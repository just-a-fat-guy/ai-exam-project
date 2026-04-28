"""上下文压缩与相关内容提取工具。

这份文件在研究能力层里的位置非常底层，但非常关键：

- retriever 找到候选来源
- browser 抓到正文
- context_manager 调用这里的压缩器
- 压缩器再把“很多正文”变成“少量高相关 context”

可以把它理解成研究阶段的“信息瘦身层”。

核心思路：
1. 把长文本切成更小的块
2. 用 embedding 相似度筛出和 query 更接近的块
3. 返回可直接喂给 LLM 的上下文
"""

import asyncio
import os
from typing import Optional

from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import (
    DocumentCompressorPipeline,
    EmbeddingsFilter,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..memory.embeddings import OPENAI_EMBEDDING_MODEL
from ..prompts import PromptFamily
from ..utils.costs import estimate_embedding_cost
from ..vector_store import VectorStoreWrapper
from .retriever import SearchAPIRetriever, SectionRetriever


class VectorstoreCompressor:
    """从向量库中检索相关上下文的压缩器。

    和 `ContextCompressor` 不同，这里不需要先切块再做 embedding，
    因为文档通常已经在更早阶段入过向量库了。
    """

    def __init__(
        self,
        vector_store: VectorStoreWrapper,
        max_results: int = 7,
        filter: Optional[dict] = None,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """初始化向量库压缩器。

        参数说明：
            vector_store:
                外部传入的向量库包装对象。
            max_results:
                默认最多返回多少条结果。
            filter:
                查询过滤条件。
            prompt_family:
                用于把召回结果格式化成字符串的 prompt family。
        """
        self.vector_store = vector_store
        self.max_results = max_results
        self.filter = filter
        self.kwargs = kwargs
        self.prompt_family = prompt_family

    async def async_get_context(self, query: str, max_results: int = 5) -> str:
        """从向量库异步获取相关上下文。

        参数说明：
            query:
                当前查询。
            max_results:
                本次最多返回多少条结果。

        返回值：
            str:
                格式化后的上下文字符串。
        """
        # 直接做向量相似度查询，不再额外走切块压缩流程。
        results = await self.vector_store.asimilarity_search(query=query, k=max_results, filter=self.filter)
        return self.prompt_family.pretty_print_docs(results)


class ContextCompressor:
    """对原始文档做切块、相似度过滤和上下文压缩。

    这个类主要服务于“网页正文 / 文档正文”这类原始内容：
    文本通常很长、噪声较多，不能直接整块喂给 LLM。
    """

    def __init__(
        self,
        documents,
        embeddings,
        max_results: int = 5,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """初始化原始文档压缩器。

        参数说明：
            documents:
                待压缩的原始文档列表。
            embeddings:
                embedding 模型实例，用于做相似度计算。
            max_results:
                默认最多保留多少条相关结果。
            prompt_family:
                最终结果格式化器。
            **kwargs:
                透传给底层检索/压缩调用的附加参数。
        """
        self.max_results = max_results
        self.documents = documents
        self.kwargs = kwargs
        self.embeddings = embeddings
        # 相似度阈值可以从环境变量覆盖，方便不同场景下调优召回强度。
        self.similarity_threshold = os.environ.get("SIMILARITY_THRESHOLD", 0.35)
        self.prompt_family = prompt_family

    def __get_contextual_retriever(self):
        """构建“切块 + embedding 过滤”的压缩管线。

        返回值：
            ContextualCompressionRetriever:
                配置好的上下文压缩检索器。

        管线结构：
            1. `RecursiveCharacterTextSplitter` 先切块
            2. `EmbeddingsFilter` 再按相似度过滤
            3. `SearchAPIRetriever` 提供原始页面文档
        """
        # 先按字符切块，避免整段正文过长导致相关内容埋在大文本里。
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        # 再按 embedding 相似度过滤，把和 query 关系更弱的块剔掉。
        relevance_filter = EmbeddingsFilter(embeddings=self.embeddings,
                                            similarity_threshold=self.similarity_threshold)
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[splitter, relevance_filter]
        )
        # 这里的 SearchAPIRetriever 不是联网检索器，而是把已有 pages 包装成可检索接口。
        base_retriever = SearchAPIRetriever(
            pages=self.documents
        )
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )
        return contextual_retriever

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> str:
        """异步获取与 query 最相关的文档上下文。

        参数说明：
            query:
                当前查询。
            max_results:
                最多保留多少条结果。
            cost_callback:
                embedding 成本统计回调。

        返回值：
            str:
                格式化后的上下文字符串。

        这里有一个非常重要的优化：
        - 如果文档总量本来就很小，就不走昂贵的 embedding 压缩流程
        - 直接把文档包装后返回，速度更快、成本更低
        """
        # 先统计总内容量，判断是否值得走压缩管线。
        total_chars = sum(len(str(doc.get('raw_content', ''))) for doc in self.documents)
        chunk_threshold = int(os.environ.get("COMPRESSION_THRESHOLD", "8000"))

        # 小文本 fast path：
        # 如果内容本来就不多，直接返回，不再做 embedding 相似度过滤。
        if total_chars < chunk_threshold and len(self.documents) <= max_results:
            direct_docs = [
                Document(
                    page_content=doc.get('raw_content', ''),
                    metadata=doc
                )
                for doc in self.documents[:max_results]
            ]
            return self.prompt_family.pretty_print_docs(direct_docs, max_results)

        # 标准路径：长文本才走“切块 + embedding 过滤”。
        compressed_docs = self.__get_contextual_retriever()
        if cost_callback:
            # 这里粗略估算 embedding 成本，便于在 UI 或日志中累计费用。
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=self.documents))
        relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)
        return self.prompt_family.pretty_print_docs(relevant_docs, max_results)


class WrittenContentCompressor:
    """对“已经写过的内容”做相似度压缩。

    这个类的场景和 `ContextCompressor` 不同：
    它不是处理网页正文，而是处理报告中已经写好的章节内容，
    目的是在续写时找到最相关的历史段落。
    """

    def __init__(self, documents, embeddings, similarity_threshold: float, **kwargs):
        """初始化“已写内容压缩器”。

        参数说明：
            documents:
                已写内容片段列表。
            embeddings:
                embedding 模型实例。
            similarity_threshold:
                相似度阈值。
        """
        self.documents = documents
        self.kwargs = kwargs
        self.embeddings = embeddings
        self.similarity_threshold = similarity_threshold

    def __get_contextual_retriever(self):
        """构建针对“章节内容”的压缩检索管线。"""
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        relevance_filter = EmbeddingsFilter(embeddings=self.embeddings,
                                            similarity_threshold=self.similarity_threshold)
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[splitter, relevance_filter]
        )
        base_retriever = SectionRetriever(
            sections=self.documents
        )
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )
        return contextual_retriever

    def __pretty_docs_list(self, docs, top_n: int) -> list[str]:
        """把相关章节格式化成“标题 + 内容”的字符串列表。

        之所以不直接返回 Document，是因为上层写作逻辑更容易消费字符串。
        """
        return [f"Title: {d.metadata.get('section_title')}\nContent: {d.page_content}\n" for i, d in enumerate(docs) if i < top_n]

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> list[str]:
        """异步获取与 query 最相关的历史已写章节。

        参数说明：
            query:
                当前查询。
            max_results:
                最多返回多少个章节片段。
            cost_callback:
                embedding 成本统计回调。

        返回值：
            list[str]:
                格式化后的相关章节列表。
        """
        compressed_docs = self.__get_contextual_retriever()
        if cost_callback:
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=self.documents))
        relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)
        return self.__pretty_docs_list(relevant_docs, max_results)
