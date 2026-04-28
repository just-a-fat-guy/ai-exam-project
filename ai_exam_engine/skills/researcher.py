"""GPT Researcher 的“研究阶段总控”模块。

如果说 `agent.py` 是整个项目的总编排器，那么这个文件就是
“研究阶段内部”的总编排器。它主要负责三件事：

1. 把用户的大问题拆成一组更可执行的子查询
2. 调度检索器、抓取器、向量库、MCP 等研究能力去收集材料
3. 把零散的搜索结果整理成后续写报告可直接消费的 `context`

学习这个文件时，建议始终围绕下面这条链路来理解：

`query -> plan_research -> sub_queries -> 搜索/抓取 -> context -> 返回给 writer`
"""

import asyncio
import logging
import os
import random

from ..actions.agent_creator import choose_agent
from ..actions.query_processing import get_search_results, plan_research_outline
from ..actions.utils import stream_output
from ..document import DocumentLoader, LangChainDocumentLoader, OnlineDocumentLoader
from ..utils.enum import ReportSource, ReportType
from ..utils.logging_config import get_json_handler


class ResearchConductor:
    """研究阶段的核心编排器。

    这个类不直接负责“最终写报告”，它只关心研究阶段本身：

    - 怎么规划研究路径
    - 怎么拆子查询
    - 怎么调用不同数据源
    - 怎么把内容整理成上下文

    你可以把它理解成 `GPTResearcher.conduct_research()` 真正委托下来的执行者。
    """

    def __init__(self, researcher):
        """初始化研究编排器。

        参数说明：
            researcher:
                上层的 `GPTResearcher` 实例。
                这里面已经包含配置、检索器、websocket、vector store、
                context manager 等所有研究阶段要用到的依赖对象。
        """
        self.researcher = researcher
        self.logger = logging.getLogger('research')
        self.json_handler = get_json_handler()

        # MCP 的 fast 模式会先对主问题跑一次 MCP，
        # 然后把结果缓存下来，供后续子查询复用，避免重复调用。
        self._mcp_results_cache = None

        # 目前主要用于统计或扩展 MCP 调度次数。
        self._mcp_query_count = 0

    async def plan_research(self, query, query_domains=None):
        """根据原始问题规划研究大纲和子查询。

        参数说明：
            query:
                当前要研究的问题。它可能是原始主问题，也可能是某一轮子问题。
            query_domains:
                域名限制列表；如果提供，初始搜索阶段只会在这些域名内找结果。

        返回值：
            list:
                由模型规划出来的一组子查询。

        这一步的核心逻辑是：
        1. 先做一次“粗搜索”，拿到初始搜索结果
        2. 再把“问题 + 搜索结果 + 当前角色”交给模型
        3. 让模型输出更适合深入研究的子查询列表
        """
        await stream_output(
            "logs",
            "planning_research",
            f"🌐 Browsing the web to learn more about the task: {query}...",
            self.researcher.websocket,
        )

        # 这里只使用当前主检索器拿第一批搜索结果。
        # 这批结果的目的不是直接拿来写报告，而是给“研究规划”提供上下文。
        search_results = await get_search_results(query, self.researcher.retrievers[0], query_domains, researcher=self.researcher)
        self.logger.info(f"Initial search results obtained: {len(search_results)} results")

        await stream_output(
            "logs",
            "planning_research",
            f"🤔 Planning the research strategy and subtasks...",
            self.researcher.websocket,
        )

        retriever_names = [r.__name__ for r in self.researcher.retrievers]
        # 这里把当前启用的 retriever 名称一起传下去，
        # 方便后面的规划逻辑根据数据源能力做更合理的子查询设计。

        outline = await plan_research_outline(
            query=query,
            search_results=search_results,
            agent_role_prompt=self.researcher.role,
            cfg=self.researcher.cfg,
            parent_query=self.researcher.parent_query,
            report_type=self.researcher.report_type,
            cost_callback=self.researcher.add_costs,
            retriever_names=retriever_names,
            **self.researcher.kwargs
        )
        self.logger.info(f"Research outline planned: {outline}")
        return outline

    async def conduct_research(self):
        """执行完整研究阶段。

        返回值：
            context:
                研究阶段产出的最终上下文，后续会直接交给写报告阶段使用。

        这是整个文件最重要的方法之一。它负责：
        1. 选择研究角色（如果上层还没选）
        2. 根据 `report_source` 决定研究从哪里取数据
        3. 组织本地文档 / 网页 / 向量库 / MCP 等研究过程
        4. 对结果做必要的 source curate
        5. 返回最终 context
        """
        if self.json_handler:
            self.json_handler.update_content("query", self.researcher.query)
        
        self.logger.info(f"Starting research for query: {self.researcher.query}")
        
        # 把当前激活的检索器记下来，后续排查“为什么结果来源不一样”时会很有用。
        retriever_names = [r.__name__ for r in self.researcher.retrievers]
        self.logger.info(f"Active retrievers: {retriever_names}")
        
        # 每轮研究开始前都清空“已访问 URL”状态，避免上一轮任务污染这一轮。
        self.researcher.visited_urls.clear()
        research_data = []

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "starting_research",
                f"🔍 Starting the research task for '{self.researcher.query}'...",
                self.researcher.websocket,
            )
            await stream_output(
                "logs",
                "agent_generated",
                self.researcher.agent,
                self.researcher.websocket
            )

        # 如果上层还没有确定 agent / role，就在研究阶段开头补选一次。
        # 这保证了后续的研究规划始终有一个明确的“研究身份”。
        if not (self.researcher.agent and self.researcher.role):
            self.researcher.agent, self.researcher.role = await choose_agent(
                query=self.researcher.query,
                cfg=self.researcher.cfg,
                parent_query=self.researcher.parent_query,
                cost_callback=self.researcher.add_costs,
                headers=self.researcher.headers,
                prompt_family=self.researcher.prompt_family
            )
                
        # 这里只是记录当前是否有 MCP retriever 参与，不改变业务逻辑。
        has_mcp_retriever = any("mcpretriever" in r.__name__.lower() for r in self.researcher.retrievers)
        if has_mcp_retriever:
            self.logger.info("MCP retrievers configured and will be used with standard research flow")

        # 根据研究来源选择不同路径。
        # 这是理解这个项目“为什么既能搜网页，又能读本地文档”的关键分支。
        if self.researcher.source_urls:
            # 如果调用方明确给了一组 URL，就优先围绕这些 URL 做研究。
            self.logger.info("Using provided source URLs")
            research_data = await self._get_context_by_urls(self.researcher.source_urls)
            if research_data and len(research_data) == 0 and self.researcher.verbose:
                await stream_output(
                    "logs",
                    "answering_from_memory",
                    f"🧐 I was unable to find relevant context in the provided sources...",
                    self.researcher.websocket,
                )
            if self.researcher.complement_source_urls:
                # 某些场景下，仅靠指定 URL 不够，因此允许再补一轮 web search。
                self.logger.info("Complementing with web search")
                additional_research = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)
                research_data += ' '.join(additional_research)
        elif self.researcher.report_source == ReportSource.Web.value:
            # 纯网页研究模式：直接走 web search 主流程。
            self.logger.info("Using web search with all configured retrievers")
            research_data = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)
        elif self.researcher.report_source == ReportSource.Local.value:
            # 本地文档模式：先把本地文档加载进来，再把它们纳入研究上下文。
            self.logger.info("Using local search")
            document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()
            self.logger.info(f"Loaded {len(document_data)} documents")
            if self.researcher.vector_store:
                # 如果配置了 vector store，就先把文档灌进去，后面可直接做向量检索。
                self.researcher.vector_store.load(document_data)

            research_data = await self._get_context_by_web_search(self.researcher.query, document_data, self.researcher.query_domains)
        # 混合模式：本地资料和网页资料都要用，最后再把两边 context 合并。
        elif self.researcher.report_source == ReportSource.Hybrid.value:
            if self.researcher.document_urls:
                document_data = await OnlineDocumentLoader(self.researcher.document_urls).load()
            else:
                document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()
            if self.researcher.vector_store:
                self.researcher.vector_store.load(document_data)
            docs_context = await self._get_context_by_web_search(self.researcher.query, document_data, self.researcher.query_domains)
            web_context = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)
            research_data = self.researcher.prompt_family.join_local_web_documents(docs_context, web_context)
        elif self.researcher.report_source == ReportSource.Azure.value:
            # Azure 文档模式本质上也是“先加载文档，再走统一上下文流程”，
            # 只是文档来源换成了 Azure Blob/容器。
            from ..document.azure_document_loader import AzureDocumentLoader
            azure_loader = AzureDocumentLoader(
                container_name=os.getenv("AZURE_CONTAINER_NAME"),
                connection_string=os.getenv("AZURE_CONNECTION_STRING")
            )
            azure_files = await azure_loader.load()
            document_data = await DocumentLoader(azure_files).load()  # Reuse existing loader
            research_data = await self._get_context_by_web_search(self.researcher.query, document_data)
            
        elif self.researcher.report_source == ReportSource.LangChainDocuments.value:
            # 允许外部直接传 LangChain 文档对象进来。
            langchain_documents_data = await LangChainDocumentLoader(
                self.researcher.documents
            ).load()
            if self.researcher.vector_store:
                self.researcher.vector_store.load(langchain_documents_data)
            research_data = await self._get_context_by_web_search(
                self.researcher.query, langchain_documents_data, self.researcher.query_domains
            )
        elif self.researcher.report_source == ReportSource.LangChainVectorStore.value:
            # 如果上层已经准备好了向量库，这里就可以绕过网页抓取，直接向量检索。
            research_data = await self._get_context_by_vectorstore(self.researcher.query, self.researcher.vector_store_filter)

        # 把研究结果暂存到 researcher.context。
        # 注意：这里的 context 还可能继续被 curate。
        self.researcher.context = research_data
        if self.researcher.cfg.curate_sources:
            # source curate 的作用是进一步对来源质量做筛选和排序，
            # 让后续写报告吃到的上下文更干净。
            self.logger.info("Curating sources")
            self.researcher.context = await self.researcher.source_curator.curate_sources(research_data)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "research_step_finalized",
                f"Finalized research step.\n💸 Total Research Costs: ${self.researcher.get_costs()}",
                self.researcher.websocket,
            )
            if self.json_handler:
                self.json_handler.update_content("costs", self.researcher.get_costs())
                self.json_handler.update_content("context", self.researcher.context)

        self.logger.info(f"Research completed. Context size: {len(str(self.researcher.context))}")
        return self.researcher.context

    async def _get_context_by_urls(self, urls):
        """围绕一组指定 URL 抓取并提炼上下文。

        参数说明：
            urls:
                调用方显式指定的网页链接列表。

        返回值：
            context:
                从这些 URL 抓取并筛选后的上下文内容。

        这个方法适合“我已经知道要看哪些网页”的场景。
        """
        self.logger.info(f"Getting context from URLs: {urls}")
        
        # 去掉已经访问过的 URL，避免重复抓取同一页面。
        new_search_urls = await self._get_new_urls(urls)
        self.logger.info(f"New URLs to process: {new_search_urls}")

        # 抓取网页正文、标题、图片等信息。
        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)
        self.logger.info(f"Scraped content from {len(scraped_content)} URLs")

        if self.researcher.vector_store:
            # 如果开启了向量库，这些抓取结果也会被同步放进去，供后续相似度检索。
            self.researcher.vector_store.load(scraped_content)

        # 不是把抓取结果原样返回，而是进一步按 query 做相关性压缩。
        context = await self.researcher.context_manager.get_similar_content_by_query(
            self.researcher.query, scraped_content
        )
        return context

    async def _get_context_by_vectorstore(self, query, filter: dict | None = None):
        """直接从向量库里为当前问题构造 context。

        参数说明：
            query:
                当前研究问题。
            filter:
                向量库过滤条件，用于限制检索范围。

        返回值：
            list:
                由各个子查询并发检索出来的上下文列表。

        这条路径和网页研究最大的区别在于：
        不需要先搜 URL 再抓网页，而是直接在向量库里做相似度查询。
        """
        self.logger.info(f"Starting vectorstore search for query: {query}")
        context = []

        # 即使是向量库检索，也不是只查一次原问题，而是先规划出多个子查询。
        sub_queries = await self.plan_research(query)

        # 非 subtopic_report 模式下，把原始问题也加入检索，通常能让召回更稳定。
        if self.researcher.report_type != "subtopic_report":
            sub_queries.append(query)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️  I will conduct my research based on the following queries: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        # 并发跑所有子查询，是这个项目“像 agent”的关键之一：
        # 一个大问题会被拆成多个研究任务同时执行。
        context = await asyncio.gather(
            *[
                self._process_sub_query_with_vectorstore(sub_query, filter)
                for sub_query in sub_queries
            ]
        )
        return context

    async def _get_context_by_web_search(self, query, scraped_data: list | None = None, query_domains: list | None = None):
        """通过“搜索 -> 抓取 -> 压缩”流程为问题生成上下文。

        参数说明：
            query:
                当前研究问题。
            scraped_data:
                已经给定的抓取数据；如果传入，就不必再重新搜 URL。
                在 local / hybrid 场景中经常会传入预加载文档。
            query_domains:
                域名限制列表。

        返回值：
            str | list:
                正常情况下会返回合并后的 context 字符串；
                如果没有结果，可能返回空列表。

        这是网页研究主流程里最核心的方法之一，主要做四件事：
        1. 处理 MCP 策略
        2. 规划子查询
        3. 并发处理每个子查询
        4. 合并所有子查询的上下文结果
        """
        self.logger.info(f"Starting web search for query: {query}")
        
        if scraped_data is None:
            scraped_data = []
        if query_domains is None:
            query_domains = []

        # 从当前检索器里识别出 MCP retriever。
        # 这里之所以单独提出来，是因为 MCP 的执行方式和普通搜索不完全一样。
        mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" in r.__name__.lower()]
        
        # 决定 MCP 是禁用、只跑一次，还是对子查询全部跑一遍。
        mcp_strategy = self._get_mcp_strategy()
        
        if mcp_retrievers and self._mcp_results_cache is None:
            if mcp_strategy == "disabled":
                # 完全禁用 MCP：整个研究流程只依赖普通 web retriever。
                self.logger.info("MCP disabled by strategy, skipping MCP research")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_disabled",
                        f"⚡ MCP research disabled by configuration",
                        self.researcher.websocket,
                    )
            elif mcp_strategy == "fast":
                # fast 模式：只对主查询跑一次 MCP，
                # 然后缓存结果，后面每个子查询直接复用缓存。
                self.logger.info("MCP fast strategy: Running once with original query")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_optimization",
                        f"🚀 MCP Fast: Running once for main query (performance mode)",
                        self.researcher.websocket,
                    )
                
                mcp_context = await self._execute_mcp_research_for_queries([query], mcp_retrievers)
                self._mcp_results_cache = mcp_context
                self.logger.info(f"MCP results cached: {len(mcp_context)} total context entries")
            elif mcp_strategy == "deep":
                # deep 模式：不提前缓存，让每个子查询都单独跑 MCP。
                # 这样成本更高，但理论上召回更全面。
                self.logger.info("MCP deep strategy: Will run for all queries")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_comprehensive",
                        f"🔍 MCP Deep: Will run for each sub-query (thorough mode)",
                        self.researcher.websocket,
                    )
            else:
                # 未知策略时保守回退到 fast，避免直接报错。
                self.logger.warning(f"Unknown MCP strategy '{mcp_strategy}', defaulting to fast")
                mcp_context = await self._execute_mcp_research_for_queries([query], mcp_retrievers)
                self._mcp_results_cache = mcp_context
                self.logger.info(f"MCP results cached: {len(mcp_context)} total context entries")

        # 先规划出研究用的子查询。
        sub_queries = await self.plan_research(query, query_domains)
        self.logger.info(f"Generated sub-queries: {sub_queries}")
        
        # 常规模式下会把原始 query 也加进去一起研究，防止子查询过于发散。
        if self.researcher.report_type != "subtopic_report":
            sub_queries.append(query)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️ I will conduct my research based on the following queries: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        # 所有子查询并发处理。每个子查询内部都会独立完成：
        # 搜索 -> 抓取 -> 相关内容筛选 -> MCP/网页上下文合并。
        try:
            context = await asyncio.gather(
                *[
                    self._process_sub_query(sub_query, scraped_data, query_domains)
                    for sub_query in sub_queries
                ]
            )
            self.logger.info(f"Gathered context from {len(context)} sub-queries")
            # 过滤掉空结果，再把所有有效 context 合成一个大上下文字符串。
            context = [c for c in context if c]
            if context:
                combined_context = " ".join(context)
                self.logger.info(f"Combined context size: {len(combined_context)}")
                return combined_context
            return []
        except Exception as e:
            self.logger.error(f"Error during web search: {e}", exc_info=True)
            return []

    def _get_mcp_strategy(self) -> str:
        """读取当前生效的 MCP 策略。

        优先级：
            1. `self.researcher.mcp_strategy`
            2. `self.researcher.cfg.mcp_strategy`
            3. 默认值 `"fast"`

        返回值：
            str:
                `"disabled"` / `"fast"` / `"deep"`
        """
        # 优先使用实例级配置，因为它通常代表本次请求的临时覆盖。
        if hasattr(self.researcher, 'mcp_strategy') and self.researcher.mcp_strategy is not None:
            return self.researcher.mcp_strategy
        
        # 否则再回退到配置文件。
        if hasattr(self.researcher.cfg, 'mcp_strategy'):
            return self.researcher.cfg.mcp_strategy
        
        # 没有任何显式配置时，默认 fast。
        return "fast"

    async def _execute_mcp_research_for_queries(self, queries: list, mcp_retrievers: list) -> list:
        """对一组 query 执行 MCP 研究，并把结果整理成统一结构。

        参数说明：
            queries:
                需要执行 MCP 研究的一组问题。
            mcp_retrievers:
                可用的 MCP retriever 类列表。

        返回值：
            list:
                统一格式的 MCP context 条目列表。每项通常包含：
                `content`、`url`、`title`、`query`、`source_type`
        """
        all_mcp_context = []
        
        for i, query in enumerate(queries, 1):
            self.logger.info(f"Executing MCP research for query {i}/{len(queries)}: {query}")
            
            for retriever in mcp_retrievers:
                try:
                    mcp_results = await self._execute_mcp_research(retriever, query)
                    if mcp_results:
                        for result in mcp_results:
                            content = result.get("body", "")
                            url = result.get("href", "")
                            title = result.get("title", "")
                            
                            if content:
                                # 统一转成内部 context entry 结构，
                                # 这样后面和 web_context 合并时不用关心来源差异。
                                context_entry = {
                                    "content": content,
                                    "url": url,
                                    "title": title,
                                    "query": query,
                                    "source_type": "mcp"
                                }
                                all_mcp_context.append(context_entry)
                        
                        self.logger.info(f"Added {len(mcp_results)} MCP results for query: {query}")
                        
                        if self.researcher.verbose:
                            await stream_output(
                                "logs",
                                "mcp_results_cached",
                                f"✅ Cached {len(mcp_results)} MCP results from query {i}/{len(queries)}",
                                self.researcher.websocket,
                            )
                except Exception as e:
                    self.logger.error(f"Error in MCP research for query '{query}': {e}")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_cache_error",
                            f"⚠️ MCP research error for query {i}, continuing with other sources",
                            self.researcher.websocket,
                        )
        
        return all_mcp_context

    async def _process_sub_query(self, sub_query: str, scraped_data: list = [], query_domains: list = []):
        """处理单个子查询，得到这个子查询对应的最终 context。

        参数说明：
            sub_query:
                当前子查询。
            scraped_data:
                外部已经准备好的抓取数据；如果为空，本方法会自己去搜索并抓取。
            query_domains:
                域名限制列表。

        返回值：
            str:
                当前子查询最终整理出来的上下文字符串。

        这是子查询执行层的核心入口。它要负责把：
        - MCP 结果
        - 普通网页搜索结果
        - 抓取后的正文
        - 相似内容筛选结果
        最终合并成一个可供写报告使用的 context。
        """
        if self.json_handler:
            self.json_handler.log_event("sub_query", {
                "query": sub_query,
                "scraped_data_size": len(scraped_data)
            })
        
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "running_subquery_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        try:
            # 把 retriever 按“是否是 MCP”拆开，后面两类处理逻辑不同。
            mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" in r.__name__.lower()]
            non_mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" not in r.__name__.lower()]
            
            # 分别承接 MCP 上下文和网页上下文，最后再统一合并。
            mcp_context = []
            web_context = ""
            
            # 读取 MCP 策略，决定这个子查询怎么用 MCP。
            mcp_strategy = self._get_mcp_strategy()
            
            if mcp_retrievers:
                if mcp_strategy == "disabled":
                    # 直接跳过 MCP，只走普通网页研究流程。
                    self.logger.info(f"MCP disabled for sub-query: {sub_query}")
                elif mcp_strategy == "fast" and self._mcp_results_cache is not None:
                    # fast 模式：这里不再重新跑 MCP，直接复用主查询阶段缓存下来的结果。
                    mcp_context = self._mcp_results_cache.copy()
                    
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_cache_reuse",
                            f"♻️ Reusing cached MCP results ({len(mcp_context)} sources) for: {sub_query}",
                            self.researcher.websocket,
                        )
                    
                    self.logger.info(f"Reused {len(mcp_context)} cached MCP results for sub-query: {sub_query}")
                elif mcp_strategy == "deep":
                    # deep 模式：每个子查询都独立跑一次 MCP。
                    self.logger.info(f"Running deep MCP research for: {sub_query}")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_comprehensive_run",
                            f"🔍 Running deep MCP research for: {sub_query}",
                            self.researcher.websocket,
                        )
                    
                    mcp_context = await self._execute_mcp_research_for_queries([sub_query], mcp_retrievers)
                else:
                    # 正常不应该走到这里；通常是 fast 模式但缓存缺失。
                    # 这里保底对当前子查询单独跑一次 MCP。
                    self.logger.warning("MCP cache not available, falling back to per-sub-query execution")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_fallback",
                            f"🔌 MCP cache unavailable, running MCP research for: {sub_query}",
                            self.researcher.websocket,
                        )
                    
                    mcp_context = await self._execute_mcp_research_for_queries([sub_query], mcp_retrievers)
            
            # 如果外部没给抓取数据，就由当前子查询自己去搜 URL 再抓内容。
            if not scraped_data:
                scraped_data = await self._scrape_data_by_urls(sub_query, query_domains)
                self.logger.info(f"Scraped data size: {len(scraped_data)}")

            # 抓到网页正文后，不是全量喂给写作，而是先做相关性筛选/压缩。
            if scraped_data:
                web_context = await self.researcher.context_manager.get_similar_content_by_query(sub_query, scraped_data)
                self.logger.info(f"Web content found for sub-query: {len(str(web_context)) if web_context else 0} chars")

            # 把 MCP 上下文和网页上下文合并成一个最终 context。
            combined_context = self._combine_mcp_and_web_context(mcp_context, web_context, sub_query)
            
            # 记录最终合并结果的规模与来源构成。
            if combined_context:
                context_length = len(str(combined_context))
                self.logger.info(f"Combined context for '{sub_query}': {context_length} chars")
                
                if self.researcher.verbose:
                    mcp_count = len(mcp_context)
                    web_available = bool(web_context)
                    cache_used = self._mcp_results_cache is not None and mcp_retrievers and mcp_strategy != "deep"
                    cache_status = " (cached)" if cache_used else ""
                    await stream_output(
                        "logs",
                        "context_combined",
                        f"📚 Combined research context: {mcp_count} MCP sources{cache_status}, {'web content' if web_available else 'no web content'}",
                        self.researcher.websocket,
                    )
            else:
                self.logger.warning(f"No combined context found for sub-query: {sub_query}")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "subquery_context_not_found",
                        f"🤷 No content found for '{sub_query}'...",
                        self.researcher.websocket,
                    )
            
            if combined_context and self.json_handler:
                self.json_handler.log_event("content_found", {
                    "sub_query": sub_query,
                    "content_size": len(str(combined_context)),
                    "mcp_sources": len(mcp_context),
                    "web_content": bool(web_context)
                })
                
            return combined_context
            
        except Exception as e:
            self.logger.error(f"Error processing sub-query {sub_query}: {e}", exc_info=True)
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "subquery_error",
                    f"❌ Error processing '{sub_query}': {str(e)}",
                    self.researcher.websocket,
                )
            return ""

    async def _execute_mcp_research(self, retriever, query):
        """使用单个 MCP retriever 对一个 query 执行研究。

        参数说明：
            retriever:
                MCP retriever 类，而不是实例。
            query:
                当前要研究的问题。

        返回值：
            list:
                MCP retriever 返回的原始结果列表。
        """
        retriever_name = retriever.__name__
        
        self.logger.info(f"Executing MCP research with {retriever_name} for query: {query}")
        
        try:
            # MCP retriever 初始化时会同时拿到 researcher，
            # 因为 researcher 里已经有 cfg、mcp_configs、websocket 等完整运行上下文。
            retriever_instance = retriever(
                query=query, 
                headers=self.researcher.headers,
                query_domains=self.researcher.query_domains,
                websocket=self.researcher.websocket,
                researcher=self.researcher
            )
            
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_retrieval_stage1",
                    f"🧠 Stage 1: Selecting optimal MCP tools for: {query}",
                    self.researcher.websocket,
                )
            
            # 真正执行 MCP 搜索。
            results = retriever_instance.search(
                max_results=self.researcher.cfg.max_search_results_per_query
            )
            
            if results:
                result_count = len(results)
                self.logger.info(f"MCP research completed: {result_count} results from {retriever_name}")
                
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_research_complete",
                        f"🎯 MCP research completed: {result_count} intelligent results obtained",
                        self.researcher.websocket,
                    )
                
                return results
            else:
                self.logger.info(f"No results returned from MCP research with {retriever_name}")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_no_results",
                        f"ℹ️ No relevant information found via MCP for: {query}",
                        self.researcher.websocket,
                    )
                return []
                
        except Exception as e:
            self.logger.error(f"Error in MCP research with {retriever_name}: {str(e)}")
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_research_error",
                    f"⚠️ MCP research error: {str(e)} - continuing with other sources",
                    self.researcher.websocket,
                )
            return []

    def _combine_mcp_and_web_context(self, mcp_context: list, web_context: str, sub_query: str) -> str:
        """把 MCP 上下文和网页上下文合并成最终上下文字符串。

        参数说明：
            mcp_context:
                MCP 返回的上下文条目列表。
            web_context:
                普通网页检索/抓取后得到的上下文字符串。
            sub_query:
                当前正在处理的子查询，仅用于日志说明。

        返回值：
            str:
                最终合并后的上下文字符串。

        当前实现的合并策略很直接：
        - 先放 web_context
        - 再格式化追加 MCP context
        - 最后拼成一个大字符串
        """
        combined_parts = []
        
        # 先放网页上下文，保证“公开网页正文”排在前面。
        if web_context and web_context.strip():
            combined_parts.append(web_context.strip())
            self.logger.debug(f"Added web context: {len(web_context)} chars")
        
        # MCP 结果需要额外格式化出来源说明，便于后续写报告时保留引用感知。
        if mcp_context:
            mcp_formatted = []
            
            for i, item in enumerate(mcp_context):
                content = item.get("content", "")
                url = item.get("url", "")
                title = item.get("title", f"MCP Result {i+1}")
                
                if content and content.strip():
                    # 对每条 MCP 结果补上来源说明；如果有 URL，就把 URL 也带上。
                    if url and url != f"mcp://llm_analysis":
                        citation = f"\n\n*Source: {title} ({url})*"
                    else:
                        citation = f"\n\n*Source: {title}*"
                    
                    formatted_content = f"{content.strip()}{citation}"
                    mcp_formatted.append(formatted_content)
            
            if mcp_formatted:
                # 不同 MCP 结果之间用分隔线隔开，避免文本粘连。
                mcp_section = "\n\n---\n\n".join(mcp_formatted)
                combined_parts.append(mcp_section)
                self.logger.debug(f"Added {len(mcp_context)} MCP context entries")
        
        # 最终统一拼成一个上下文字符串。
        if combined_parts:
            final_context = "\n\n".join(combined_parts)
            self.logger.info(f"Combined context for '{sub_query}': {len(final_context)} total chars")
            return final_context
        else:
            self.logger.warning(f"No context to combine for sub-query: {sub_query}")
            return ""

    async def _process_sub_query_with_vectorstore(self, sub_query: str, filter: dict | None = None):
        """用向量库处理单个子查询。

        参数说明：
            sub_query:
                由主问题拆出来的一个子查询。
            filter:
                向量库过滤条件。

        返回值：
            str:
                从向量库里检索出来的相关上下文。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "running_subquery_with_vectorstore_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        context = await self.researcher.context_manager.get_similar_content_by_query_with_vectorstore(sub_query, filter)

        return context

    async def _get_new_urls(self, url_set_input):
        """从一组 URL 中筛出“当前还没访问过”的新 URL。

        参数说明：
            url_set_input:
                待处理的 URL 集合或列表。

        返回值：
            list[str]:
                本轮真正需要抓取的新 URL 列表。

        这个方法的意义很实际：
        避免多个子查询反复抓同一批页面，减少重复工作和请求成本。
        """

        new_urls = []
        for url in url_set_input:
            if url not in self.researcher.visited_urls:
                # 只要决定要处理，就立刻记进 visited_urls，
                # 防止后续别的子查询重复加入。
                self.researcher.visited_urls.add(url)
                new_urls.append(url)
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "added_source_url",
                        f"✅ Added source url to research: {url}\n",
                        self.researcher.websocket,
                        True,
                        url,
                    )

        return new_urls

    async def _search_relevant_source_urls(self, query, query_domains: list | None = None):
        """让当前所有非 MCP retriever 为某个 query 搜 URL。

        参数说明：
            query:
                当前子查询。
            query_domains:
                域名限制列表。

        返回值：
            list[str]:
                去重、过滤、打乱顺序后的新 URL 列表。

        这里的重点是：
        - 会遍历当前已启用的所有普通 retriever
        - 不会让 MCP retriever 参与，因为 MCP 返回的不是待抓取 URL
        """
        new_search_urls = []
        if query_domains is None:
            query_domains = []

        # 遍历当前启用的检索器列表。
        # 这样即使上层临时改了 retriever 组合，这里也能自动适配。
        for retriever_class in self.researcher.retrievers:
            # MCP 检索器不提供网页 URL，因此不参与这一段“搜 URL -> 抓网页”的流程。
            if "mcpretriever" in retriever_class.__name__.lower():
                continue
                
            try:
                # 用当前子查询实例化 retriever。
                retriever = retriever_class(query, query_domains=query_domains)

                # 某些 retriever.search 是同步方法，所以放到线程里执行。
                search_results = await asyncio.to_thread(
                    retriever.search, max_results=self.researcher.cfg.max_search_results_per_query
                )

                # 从检索结果里把 href 抽出来。
                search_urls = [url.get("href") for url in search_results if url.get("href")]
                new_search_urls.extend(search_urls)
            except Exception as e:
                self.logger.error(f"Error searching with {retriever_class.__name__}: {e}")

        # 对 URL 去重，并过滤掉已访问过的。
        new_search_urls = await self._get_new_urls(new_search_urls)

        # 打乱一下顺序，避免总是按同一来源顺序抓取。
        random.shuffle(new_search_urls)

        return new_search_urls

    async def _scrape_data_by_urls(self, sub_query, query_domains: list | None = None):
        """为一个子查询完成“找 URL + 抓正文”。

        参数说明：
            sub_query:
                当前子查询。
            query_domains:
                域名限制列表。

        返回值：
            list:
                抓取结果列表。每项通常包含标题、正文、图片、URL 等信息。
        """
        if query_domains is None:
            query_domains = []

        # 先从多个普通检索器里收集一批相关 URL。
        new_search_urls = await self._search_relevant_source_urls(sub_query, query_domains)

        # Log the research process if verbose mode is on
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "researching",
                f"🤔 Researching for relevant information across multiple sources...\n",
                self.researcher.websocket,
            )

        # 再把这些 URL 交给 scraper manager 统一抓取。
        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)

        if self.researcher.vector_store:
            # 如果有向量库，抓完立刻入库，便于后面相似度筛选或后续检索复用。
            self.researcher.vector_store.load(scraped_content)

        return scraped_content

    async def _search(self, retriever, query):
        """用指定 retriever 执行一次搜索。

        参数说明：
            retriever:
                要使用的 retriever 类。
            query:
                查询文本。

        返回值：
            list:
                搜索结果列表。

        这个方法更偏底层封装，主要作用是统一：
        - retriever 的实例化方式
        - MCP / 非 MCP 检索器的日志差异
        - 错误处理方式
        """
        retriever_name = retriever.__name__
        is_mcp_retriever = "mcpretriever" in retriever_name.lower()
        
        self.logger.info(f"Searching with {retriever_name} for query: {query}")
        
        try:
            # MCP retriever 需要 researcher / websocket 等额外上下文；
            # 普通 retriever 只需要 query、headers、query_domains 即可。
            retriever_instance = retriever(
                query=query, 
                headers=self.researcher.headers,
                query_domains=self.researcher.query_domains,
                websocket=self.researcher.websocket if is_mcp_retriever else None,
                researcher=self.researcher if is_mcp_retriever else None
            )
            
            # MCP retriever 会额外输出一段“正在咨询 MCP server”的日志，
            # 方便前端把这类来源和普通网页搜索区分开。
            if is_mcp_retriever and self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_retrieval",
                    f"🔌 Consulting MCP server(s) for information on: {query}",
                    self.researcher.websocket,
                )
            
            # 统一调用 search 方法拿结果。
            if hasattr(retriever_instance, 'search'):
                results = retriever_instance.search(
                    max_results=self.researcher.cfg.max_search_results_per_query
                )
                
                # 根据结果数量和来源类型输出日志。
                if results:
                    result_count = len(results)
                    self.logger.info(f"Received {result_count} results from {retriever_name}")
                    
                    # MCP retriever 会额外记录前几条结果，便于调试。
                    if is_mcp_retriever:
                        if self.researcher.verbose:
                            await stream_output(
                                "logs",
                                "mcp_results",
                                f"✓ Retrieved {result_count} results from MCP server",
                                self.researcher.websocket,
                            )
                        
                        for i, result in enumerate(results[:3]):  # Log first 3 results
                            title = result.get("title", "No title")
                            url = result.get("href", "No URL")
                            content_length = len(result.get("body", "")) if result.get("body") else 0
                            self.logger.info(f"MCP result {i+1}: '{title}' from {url} ({content_length} chars)")
                            
                        if result_count > 3:
                            self.logger.info(f"... and {result_count - 3} more MCP results")
                else:
                    self.logger.info(f"No results returned from {retriever_name}")
                    if is_mcp_retriever and self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_no_results",
                            f"ℹ️ No relevant information found from MCP server for: {query}",
                            self.researcher.websocket,
                        )
                
                return results
            else:
                self.logger.error(f"Retriever {retriever_name} does not have a search method")
                return []
        except Exception as e:
            self.logger.error(f"Error searching with {retriever_name}: {str(e)}")
            if is_mcp_retriever and self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_error",
                    f"❌ Error retrieving information from MCP server: {str(e)}",
                    self.researcher.websocket,
                )
            return []
            
    async def _extract_content(self, results):
        """从搜索结果里提取 URL 并抓取正文内容。

        参数说明：
            results:
                搜索结果列表。

        返回值：
            list:
                抓取出来的正文内容列表。

        这是一层很薄的辅助封装：
        搜索结果 -> 提取 href -> 去重 -> 抓网页
        """
        self.logger.info(f"Extracting content from {len(results)} search results")
        
        # 先从搜索结果里把 URL 抽出来。
        urls = []
        for result in results:
            if isinstance(result, dict) and "href" in result:
                urls.append(result["href"])
        
        # 没有 URL 就没有后续抓取必要。
        if not urls:
            return []
            
        # 过滤掉已经访问过的 URL。
        new_urls = [url for url in urls if url not in self.researcher.visited_urls]
        
        # 如果都是旧 URL，也没必要重复抓。
        if not new_urls:
            return []
            
        # 统一抓取正文。
        scraped_content = await self.researcher.scraper_manager.browse_urls(new_urls)
        
        # 抓过之后记入 visited_urls，避免后续重复。
        self.researcher.visited_urls.update(new_urls)
        
        return scraped_content
        
    async def _summarize_content(self, query, content):
        """对已提取内容做一轮基于 query 的压缩/摘要。

        参数说明：
            query:
                当前查询。
            content:
                已抓取的内容列表。

        返回值：
            str:
                摘要或压缩后的上下文字符串。
        """
        self.logger.info(f"Summarizing content for query: {query}")
        
        # 没有内容时直接返回空字符串。
        if not content:
            return ""
            
        # 这里本质上还是借助 context_manager 做“与 query 相关的内容筛选”，
        # 不是一个独立的大模型摘要系统。
        summary = await self.researcher.context_manager.get_similar_content_by_query(
            query, content
        )
        
        return summary
        
    async def _update_search_progress(self, current, total):
        """把研究进度推送给前端。

        参数说明：
            current:
                当前已经处理完的子查询数量。
            total:
                子查询总数。
        """
        if self.researcher.verbose and self.researcher.websocket:
            progress = int((current / total) * 100)
            await stream_output(
                "logs",
                "research_progress",
                f"📊 Research Progress: {progress}%",
                self.researcher.websocket,
                True,
                {
                    "current": current,
                    "total": total,
                    "progress": progress
                }
            )
