"""上下文管理器。

研究能力层里最关键的一件事不是“抓到多少内容”，而是：
抓到的内容里哪些真的和当前问题相关。

这个文件就是专门处理这件事的：
- 从抓到的页面里筛相关内容
- 从向量库里取相关内容
- 从已写内容里找相似段落
"""

import asyncio
from typing import Dict, List, Optional, Set

from ..actions.utils import stream_output
from ..context.compression import (
    ContextCompressor,
    VectorstoreCompressor,
    WrittenContentCompressor,
)


class ContextManager:
    """研究阶段的上下文筛选与压缩控制器。

    你可以把它理解成“研究内容的二次过滤层”：
    - BrowserManager 负责抓正文
    - ContextManager 负责把正文压缩成真正有用的 context
    """

    def __init__(self, researcher):
        """初始化上下文管理器。

        参数说明：
            researcher:
                上层 `GPTResearcher` 实例。
                这里主要会用到：
                - memory.get_embeddings()
                - prompt_family
                - vector_store
                - websocket / verbose
        """
        self.researcher = researcher

    async def get_similar_content_by_query(self, query: str, pages: list) -> str:
        """从抓取到的页面内容里筛出与 query 最相关的上下文。

        参数说明：
            query:
                当前问题或子查询。
            pages:
                已抓取页面列表。

        返回值：
            str:
                压缩后的相关上下文字符串。

        这里并不是简单拼接所有页面正文，而是交给 `ContextCompressor`
        做 embedding 相似度过滤。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "fetching_query_content",
                f"📚 Getting relevant content based on query: {query}...",
                self.researcher.websocket,
            )

        # ContextCompressor 会把页面切块、向量过滤，再格式化输出。
        context_compressor = ContextCompressor(
            documents=pages,
            embeddings=self.researcher.memory.get_embeddings(),
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )
        return await context_compressor.async_get_context(
            query=query, max_results=10, cost_callback=self.researcher.add_costs
        )

    async def get_similar_content_by_query_with_vectorstore(self, query: str, filter: dict | None) -> str:
        """从向量库中直接取与 query 相似的上下文。

        参数说明：
            query:
                当前问题或子查询。
            filter:
                可选过滤条件，用于限制向量库召回范围。

        返回值：
            str:
                从向量库里取到并格式化后的上下文字符串。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "fetching_query_format",
                f" Getting relevant content based on query: {query}...",
                self.researcher.websocket,
                )
        # VectorstoreCompressor 不再走“网页切块压缩”，而是直接做向量检索。
        vectorstore_compressor = VectorstoreCompressor(
            self.researcher.vector_store, filter=filter, prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )
        return await vectorstore_compressor.async_get_context(query=query, max_results=8)

    async def get_similar_written_contents_by_draft_section_titles(
        self,
        current_subtopic: str,
        draft_section_titles: List[str],
        written_contents: List[Dict],
        max_results: int = 10
    ) -> List[str]:
        """从“已经写过的内容”里找到和当前子主题最相关的段落。

        参数说明：
            current_subtopic:
                当前正在写的子主题。
            draft_section_titles:
                当前子主题下的草稿章节标题列表。
            written_contents:
                已写好的内容片段集合。
            max_results:
                最多返回多少条相关内容。

        返回值：
            List[str]:
                从历史已写内容里筛出来的相关片段。

        这类能力主要用于：
        - 子主题续写
        - 避免内容重复
        - 保持不同章节之间的衔接
        """
        # 把“当前子主题 + 各章节标题”都视为检索 query，一起去找相似的已写内容。
        all_queries = [current_subtopic] + draft_section_titles

        async def process_query(query: str) -> Set[str]:
            return set(await self.__get_similar_written_contents_by_query(query, written_contents, **self.researcher.kwargs))

        results = await asyncio.gather(*[process_query(query) for query in all_queries])
        relevant_contents = set().union(*results)
        relevant_contents = list(relevant_contents)[:max_results]

        return relevant_contents

    async def __get_similar_written_contents_by_query(
        self,
        query: str,
        written_contents: List[Dict],
        similarity_threshold: float = 0.5,
        max_results: int = 10
    ) -> List[str]:
        """针对单个 query，从已写内容中找相似段落。

        参数说明：
            query:
                单个检索 query。
            written_contents:
                已写内容集合。
            similarity_threshold:
                相似度阈值，低于这个值的内容不会被保留。
            max_results:
                最多返回多少条结果。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "fetching_relevant_written_content",
                f"🔎 Getting relevant written content based on query: {query}...",
                self.researcher.websocket,
            )

        # WrittenContentCompressor 是“已写内容场景”的专用压缩器。
        written_content_compressor = WrittenContentCompressor(
            documents=written_contents,
            embeddings=self.researcher.memory.get_embeddings(),
            similarity_threshold=similarity_threshold,
            **self.researcher.kwargs
        )
        return await written_content_compressor.async_get_context(
            query=query, max_results=max_results, cost_callback=self.researcher.add_costs
        )
