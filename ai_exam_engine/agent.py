"""GPT Researcher 的主编排模块。

学习这个文件时，最重要的判断不是“每个属性都在干什么”，而是：

1. `GPTResearcher` 为什么是整个项目的统一入口
2. 它自己做了哪些事，哪些事又委托给别的组件
3. 为什么主链路要拆成 `conduct_research()` 和 `write_report()` 两步

你可以把这个类理解成一个总控对象：

- 输入层：接收 query、报告类型、来源、语气、MCP 配置等参数
- 研究层：把研究任务交给 `ResearchConductor`
- 写作层：把报告生成交给 `ReportGenerator`
- 基础设施层：统一持有配置、检索器、记忆、日志、成本统计等状态
"""

import json
import os
from typing import Any, Optional

from .actions import (
    add_references,
    choose_agent,
    extract_headers,
    extract_sections,
    get_retrievers,
    get_search_results,
    table_of_contents,
)
from .config import Config
from .llm_provider import GenericLLMProvider
from .memory import Memory
from .prompts import get_prompt_family
from .skills.browser import BrowserManager
from .skills.context_manager import ContextManager
from .skills.curator import SourceCurator
from .skills.deep_research import DeepResearchSkill
from .skills.image_generator import ImageGenerator
from .skills.researcher import ResearchConductor
from .skills.writer import ReportGenerator
from .utils.enum import ReportSource, ReportType, Tone
from .utils.llm import create_chat_completion
from .vector_store import VectorStoreWrapper


class GPTResearcher:
    """GPT Researcher 的主入口类。

    它的核心职责是“编排”而不是“包办”：

    - 检索和研究流程主要交给 `ResearchConductor`
    - 写报告主要交给 `ReportGenerator`
    - 抓取网页交给 `BrowserManager`
    - 上下文压缩与相似度筛选交给 `ContextManager`

    因此读这个类时，不要把它当成一个“所有逻辑都堆在一起”的大类，
    而要把它看成整个系统的总调度中心。
    """

    def __init__(
        self,
        query: str,
        report_type: str = ReportType.ResearchReport.value,
        report_format: str = "markdown",
        report_source: str = ReportSource.Web.value,
        tone: Tone = Tone.Objective,
        source_urls: list[str] | None = None,
        document_urls: list[str] | None = None,
        complement_source_urls: bool = False,
        query_domains: list[str] | None = None,
        documents=None,
        vector_store=None,
        vector_store_filter=None,
        config_path=None,
        websocket=None,
        agent=None,
        role=None,
        parent_query: str = "",
        subtopics: list | None = None,
        visited_urls: set | None = None,
        verbose: bool = True,
        context=None,
        headers: dict | None = None,
        max_subtopics: int = 5,
        log_handler=None,
        prompt_family: str | None = None,
        mcp_configs: list[dict] | None = None,
        mcp_max_iterations: int | None = None,
        mcp_strategy: str | None = None,
        **kwargs
    ):
        """初始化一个 GPTResearcher 实例。

        参数说明可以按“用途分组”理解，而不要孤立地逐个硬背：

        一、任务定义参数
            query:
                用户真正要研究的问题，是整条主链路的起点。
            report_type:
                报告类型，决定最终走哪种报告生成策略。
            report_format:
                最终报告格式，常见是 markdown，也可能扩展到其他格式。
            report_source:
                研究资料来源，例如 web / local / hybrid。
            tone:
                报告语气，例如客观、正式、分析型等。

        二、输入数据与检索范围参数
            source_urls:
                显式指定的一批网页链接；如果传入，研究阶段会优先从这些链接取内容。
            document_urls:
                在线文档链接列表，适合给定 PDF、网页文档等外部资料。
            complement_source_urls:
                当已经给了 source_urls 时，是否还要额外补一轮 web search。
            query_domains:
                域名白名单；只在这些域名范围内检索，可以明显影响结果质量。
            documents:
                直接传入的文档对象，常用于 LangChain 集成或上层系统封装。
            vector_store:
                外部传入的向量库；如果有它，项目可直接做向量检索而不必全靠网页搜索。
            vector_store_filter:
                向量库查询过滤条件，用于控制检索范围。

        三、运行环境与上下文参数
            config_path:
                配置文件路径；最终会交给 `Config` 读取。
            websocket:
                前端或调用方的流式输出通道；日志、研究进度、报告片段都会走这里。
            headers:
                自定义请求头或其他额外配置，常用于对接外部服务。
            verbose:
                是否输出更详细的研究过程日志。
            context:
                已有上下文；如果调用方已经准备好部分研究材料，可以从这里继续。
            visited_urls:
                已访问 URL 集合；用于避免重复抓取。

        四、角色与子任务参数
            agent:
                预先指定的研究代理名称；不传时系统会自动选择。
            role:
                预先指定的研究角色提示词；不传时系统会自动选择。
            parent_query:
                父问题，常用于 subtopic_report 等场景。
            subtopics:
                已经拆好的子主题列表。
            max_subtopics:
                自动规划子主题时的上限。

        五、可扩展能力参数
            log_handler:
                自定义日志处理器。
            prompt_family:
                prompt 家族配置；用于替换默认提示词模板。
            mcp_configs:
                MCP server 配置列表。每项通常包含 command / args / env 等信息。
            mcp_max_iterations:
                旧版 MCP 配置参数，主要用于向后兼容。
            mcp_strategy:
                新版 MCP 执行策略：
                - fast: 只对主查询跑一次，性能优先
                - deep: 对所有子查询都跑，全面性优先
                - disabled: 完全禁用 MCP

        六、其他透传参数
            **kwargs:
                额外参数透传给底层 LLM / action 层使用。
                这里常放一些上层框架希望继续往下传的临时扩展配置。
        """
        # 保存额外透传参数。后面很多 action / LLM 调用会继续使用这些 kwargs。
        self.kwargs = kwargs

        # ------------------------------
        # 任务的最小核心状态
        # ------------------------------
        self.query = query
        self.report_type = report_type
        self.cfg = Config(config_path)
        self.cfg.set_verbose(verbose)
        self.report_source = report_source if report_source else getattr(self.cfg, 'report_source', None)
        self.report_format = report_format
        self.max_subtopics = max_subtopics
        self.tone = tone if isinstance(tone, Tone) else Tone.Objective

        # ------------------------------
        # 输入来源与研究范围控制
        # ------------------------------
        self.source_urls = source_urls
        self.document_urls = document_urls
        self.complement_source_urls = complement_source_urls
        self.query_domains = query_domains or []
        self.research_sources = []  # The list of scraped sources including title, content and images
        self.research_images = []  # The list of selected research images
        self.documents = documents
        self.vector_store = VectorStoreWrapper(vector_store) if vector_store else None
        self.vector_store_filter = vector_store_filter

        # ------------------------------
        # 调用环境、角色、上下文
        # ------------------------------
        self.websocket = websocket
        self.agent = agent
        self.role = role
        self.parent_query = parent_query
        self.subtopics = subtopics or []
        self.visited_urls = visited_urls or set()
        self.verbose = verbose
        self.context = context or []
        self.headers = headers or {}
        self.research_costs = 0.0
        self.step_costs: dict[str, float] = {}
        self._current_step: str = "general"
        self.log_handler = log_handler
        self.prompt_family = get_prompt_family(prompt_family or self.cfg.prompt_family, self.cfg)
        
        # 如果外部传入了 MCP server 配置，就在初始化阶段先处理好。
        # 这样后续构造 retriever 时就能把 MCP 能力纳入整体研究流程。
        self.mcp_configs = mcp_configs
        if mcp_configs:
            self._process_mcp_configs(mcp_configs)
        
        # 检索器与向量记忆属于“基础设施”，它们本身不是主链路，
        # 但后面的研究阶段几乎都会用到。
        self.retrievers = get_retrievers(self.headers, self.cfg)
        self.memory = Memory(
            self.cfg.embedding_provider, self.cfg.embedding_model, **self.cfg.embedding_kwargs
        )
        
        # encoding 更多是本地文件与部分 I/O 环节需要的参数，
        # 不是底层 LLM API 的标准参数，所以会从 kwargs 中移除。
        self.encoding = kwargs.get('encoding', 'utf-8')
        self.kwargs.pop('encoding', None)

        # 初始化各个真正做事的组件。
        # 这几行是理解本类“只负责编排”的关键证据：
        # 真正的研究、写作、抓取、上下文整理，都分发给了别的对象。
        self.research_conductor: ResearchConductor = ResearchConductor(self)
        self.report_generator: ReportGenerator = ReportGenerator(self)
        self.context_manager: ContextManager = ContextManager(self)
        self.scraper_manager: BrowserManager = BrowserManager(self)
        self.source_curator: SourceCurator = SourceCurator(self)
        self.deep_researcher: Optional[DeepResearchSkill] = None
        if report_type == ReportType.DeepResearch.value:
            self.deep_researcher = DeepResearchSkill(self)

        # 图像生成属于可选能力，不是主链路必需部分。
        self.image_generator: Optional[ImageGenerator] = ImageGenerator(self)
        self.available_images: list = []  # 研究阶段预生成好、写报告时可直接嵌入的图片
        self._research_id: str = ""  # 本次研究任务的唯一 ID

        # 统一解析 MCP 策略，同时兼容旧参数命名。
        self.mcp_strategy = self._resolve_mcp_strategy(mcp_strategy, mcp_max_iterations)
    
    def _generate_research_id(self) -> str:
        """为当前研究会话生成唯一 ID。

        返回值：
            str: 当前研究任务的唯一标识。

        这个 ID 主要用于：
        1. 区分不同研究任务
        2. 关联图像生成等需要“任务级别标识”的功能
        """
        if not self._research_id:
            import hashlib
            import time
            # Create unique ID from query + timestamp
            unique_str = f"{self.query}_{time.time()}"
            self._research_id = f"research_{hashlib.md5(unique_str.encode()).hexdigest()[:12]}"
        return self._research_id

    def _resolve_mcp_strategy(self, mcp_strategy: str | None, mcp_max_iterations: int | None) -> str:
        """解析 MCP 执行策略，并兼容旧版配置方式。

        参数说明：
            mcp_strategy:
                新版 MCP 策略参数，优先级最高。
            mcp_max_iterations:
                旧版参数，保留仅为兼容旧调用方。

        返回值：
            str:
                最终生效的 MCP 策略，只会是 `"fast"`、`"deep"`、
                `"disabled"` 三者之一。

        优先级顺序：
            1. 调用时显式传入的 `mcp_strategy`
            2. 旧参数 `mcp_max_iterations`
            3. 配置文件中的 MCP_STRATEGY
            4. 默认值 `"fast"`
        """
        # Priority 1: Use mcp_strategy parameter if provided
        if mcp_strategy is not None:
            # Support new strategy names
            if mcp_strategy in ["fast", "deep", "disabled"]:
                return mcp_strategy
            # Support old strategy names for backwards compatibility
            elif mcp_strategy == "optimized":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'optimized' is deprecated, use 'fast' instead")
                return "fast"
            elif mcp_strategy == "comprehensive":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'comprehensive' is deprecated, use 'deep' instead")
                return "deep"
            else:
                import logging
                logging.getLogger(__name__).warning(f"Invalid mcp_strategy '{mcp_strategy}', defaulting to 'fast'")
                return "fast"
        
        # Priority 2: Convert mcp_max_iterations for backwards compatibility
        if mcp_max_iterations is not None:
            import logging
            logging.getLogger(__name__).warning("mcp_max_iterations is deprecated, use mcp_strategy instead")
            
            if mcp_max_iterations == 0:
                return "disabled"
            elif mcp_max_iterations == 1:
                return "fast"
            elif mcp_max_iterations == -1:
                return "deep"
            else:
                # Treat any other number as fast mode
                return "fast"
        
        # Priority 3: Use config setting
        if hasattr(self.cfg, 'mcp_strategy'):
            config_strategy = self.cfg.mcp_strategy
            # Support new strategy names
            if config_strategy in ["fast", "deep", "disabled"]:
                return config_strategy
            # Support old strategy names for backwards compatibility
            elif config_strategy == "optimized":
                return "fast"
            elif config_strategy == "comprehensive":
                return "deep"
            
        # Priority 4: Default to fast
        return "fast"

    def _process_mcp_configs(self, mcp_configs: list[dict]) -> None:
        """处理 MCP 配置，并在必要时把 MCP 加入 retriever 列表。

        参数说明：
            mcp_configs:
                MCP server 配置列表，每一项通常描述如何连接一个 MCP 服务。

        这个函数的关键点是：
        - 如果用户已经显式设置了 `RETRIEVER` 环境变量，就尊重用户配置
        - 如果用户没有显式设置，而又传入了 MCP 配置，就自动把 `mcp`
          加到当前检索器列表里
        """
        # Check if user explicitly set RETRIEVER environment variable
        user_set_retriever = os.getenv("RETRIEVER") is not None
        
        if not user_set_retriever:
            # Only auto-add MCP if user hasn't explicitly set retrievers
            if hasattr(self.cfg, 'retrievers') and self.cfg.retrievers:
                # If retrievers is set in config (but not via env var)
                current_retrievers = set(self.cfg.retrievers.split(",")) if isinstance(self.cfg.retrievers, str) else set(self.cfg.retrievers)
                if "mcp" not in current_retrievers:
                    current_retrievers.add("mcp")
                    self.cfg.retrievers = ",".join(filter(None, current_retrievers))
            else:
                # No retrievers configured, use mcp as default
                self.cfg.retrievers = "mcp"
        # If user explicitly set RETRIEVER, respect their choice and don't auto-add MCP
        
        # Store the mcp_configs for use by the MCP retriever
        self.mcp_configs = mcp_configs

    async def _log_event(self, event_type: str, **kwargs):
        """统一处理日志事件。

        参数说明：
            event_type:
                事件类型，目前常见有 `tool`、`action`、`research`。
            **kwargs:
                事件附加信息，会根据事件类型发给不同的日志处理器。

        这个方法的作用是把“日志怎么发”从主流程中抽离出来，
        这样 `conduct_research()` / `write_report()` 之类的方法就能专注于业务本身。
        """
        if self.log_handler:
            try:
                if event_type == "tool":
                    await self.log_handler.on_tool_start(kwargs.get('tool_name', ''), **kwargs)
                elif event_type == "action":
                    await self.log_handler.on_agent_action(kwargs.get('action', ''), **kwargs)
                elif event_type == "research":
                    await self.log_handler.on_research_step(kwargs.get('step', ''), kwargs.get('details', {}))

                # Add direct logging as backup
                import logging
                research_logger = logging.getLogger('research')
                research_logger.info(f"{event_type}: {json.dumps(kwargs, default=str)}")

            except Exception as e:
                import logging
                logging.getLogger('research').error(f"Error in _log_event: {e}", exc_info=True)

    async def conduct_research(self, on_progress=None):
        """执行研究阶段。

        参数说明：
            on_progress:
                可选的进度回调，主要给 deep research 这种长流程模式使用。

        返回值：
            context:
                研究阶段最终产出的上下文内容。后续 `write_report()` 会直接消费它。

        这一步是主链路的前半段，主要负责：
            1. 记录研究开始日志
            2. 如有需要，自动选择 agent / role
            3. 调用 `ResearchConductor.conduct_research()`
            4. 保存最终 context
            5. 如启用图片生成，则预生成可嵌入报告的图片
        """
        await self._log_event("research", step="start", details={
            "query": self.query,
            "report_type": self.report_type,
            "agent": self.agent,
            "role": self.role
        })

        # `deep_research` 是特殊模式，执行逻辑和普通研究不同，
        # 所以单独分流到专门的方法里处理。
        if self.report_type == ReportType.DeepResearch.value and self.deep_researcher:
            self._current_step = "deep_research"
            return await self._handle_deep_research(on_progress)

        if not (self.agent and self.role):
            # 如果调用方没有提前指定“研究员身份”和“角色提示词”，
            # 就在这里让模型动态选择。
            self._current_step = "agent_selection"
            await self._log_event("action", action="choose_agent")
            self.agent, self.role = await choose_agent(
                query=self.query,
                cfg=self.cfg,
                parent_query=self.parent_query,
                cost_callback=self.add_costs,
                headers=self.headers,
                prompt_family=self.prompt_family,
                **self.kwargs,
            )
            await self._log_event("action", action="agent_selected", details={
                "agent": self.agent,
                "role": self.role
            })

        await self._log_event("research", step="conducting_research", details={
            "agent": self.agent,
            "role": self.role
        })
        self._current_step = "research"

        # 真正进入研究主流程。
        # 这里再次体现了本类的定位：它不亲自实现研究细节，而是把任务交给
        # `ResearchConductor`，自己只负责衔接前后状态。
        self.context = await self.research_conductor.conduct_research()

        await self._log_event("research", step="research_completed", details={
            "context_length": len(self.context)
        })
        
        # 如果启用了图像能力，则在研究阶段结束后先做图像规划/生成。
        # 这样等到写报告时，图片已经准备好，可以直接嵌入，前端体验更顺畅。
        self.available_images = []
        if self.image_generator and self.image_generator.is_enabled():
            await self._log_event("research", step="planning_images")
            # 图像规划需要整体上下文，因此这里把 list 形式的 context 拼成字符串。
            context_str = "\n\n".join(self.context) if isinstance(self.context, list) else str(self.context)
            self.available_images = await self.image_generator.plan_and_generate_images(
                context=context_str,
                query=self.query,
                research_id=self._generate_research_id(),
            )
            await self._log_event("research", step="images_pre_generated", details={
                "images_count": len(self.available_images)
            })
        
        return self.context

    async def _handle_deep_research(self, on_progress=None):
        """执行深度研究模式。

        参数说明：
            on_progress:
                深度研究过程的进度回调。

        返回值：
            context:
                深度研究模式产出的上下文。

        普通研究模式与 deep research 的差别主要在于：
        - 分支更深
        - 并发与广度/深度控制更复杂
        - 成本与日志通常也更重
        """
        # Log deep research configuration
        await self._log_event("research", step="deep_research_initialize", details={
            "type": "deep_research",
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # Log deep research start
        await self._log_event("research", step="deep_research_start", details={
            "query": self.query,
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # Run deep research and get context
        self.context = await self.deep_researcher.run(on_progress=on_progress)

        # Get total research costs
        total_costs = self.get_costs()

        # Log deep research completion with costs
        await self._log_event("research", step="deep_research_complete", details={
            "context_length": len(self.context),
            "visited_urls": len(self.visited_urls),
            "total_costs": total_costs
        })

        # Log final cost update
        await self._log_event("research", step="cost_update", details={
            "cost": total_costs,
            "total_cost": total_costs,
            "research_type": "deep_research"
        })

        # Return the research context
        return self.context

    async def write_report(
        self,
        existing_headers: list = [],
        relevant_written_contents: list = [],
        ext_context=None,
        custom_prompt="",
    ) -> str:
        """执行写报告阶段。

        参数说明：
            existing_headers:
                已经写过的标题列表，主要用于避免重复标题。
                在分段写作、子主题写作等场景里更常见。
            relevant_written_contents:
                已写过的相关内容，用于让后续写作更连贯。
            ext_context:
                外部传入的上下文；如果提供，则优先使用它，而不是内部研究结果。
            custom_prompt:
                额外的自定义提示词，用于覆盖或补充默认写作指令。

        返回值：
            str: 最终生成的报告文本。

        这一步是主链路的后半段，主要负责：
            1. 记录写作开始日志
            2. 把研究阶段产出的 context 交给 `ReportGenerator`
            3. 如有图片，则一起传给写作阶段
            4. 记录写作完成日志并返回报告文本
        """
        # 判断研究阶段是否已经准备好了可用图片。
        has_available_images = bool(self.available_images)
        
        self._current_step = "report_writing"
        await self._log_event("research", step="writing_report", details={
            "existing_headers": existing_headers,
            "context_source": "external" if ext_context else "internal",
            "available_images_count": len(self.available_images),
        })

        # 把真正的写作动作委托给 ReportGenerator。
        # 这也是理解职责边界的关键：
        # - agent.py 负责调度
        # - writer.py 负责写作过程控制
        report = await self.report_generator.write_report(
            existing_headers=existing_headers,
            relevant_written_contents=relevant_written_contents,
            ext_context=ext_context or self.context,
            custom_prompt=custom_prompt,
            available_images=self.available_images,
        )

        await self._log_event("research", step="report_completed", details={
            "report_length": len(report),
            "images_embedded": len(self.available_images) if has_available_images else 0,
        })
        return report

    async def write_report_conclusion(self, report_body: str) -> str:
        """只写报告结论部分。

        参数说明：
            report_body:
                已经存在的正文内容，结论会基于它来收束。

        返回值：
            str: 生成出来的结论文本。
        """
        await self._log_event("research", step="writing_conclusion")
        conclusion = await self.report_generator.write_report_conclusion(report_body)
        await self._log_event("research", step="conclusion_completed")
        return conclusion

    async def write_introduction(self) -> str:
        """只写报告引言部分。

        返回值：
            str: 生成出来的引言文本。
        """
        await self._log_event("research", step="writing_introduction")
        intro = await self.report_generator.write_introduction()
        await self._log_event("research", step="introduction_completed")
        return intro

    async def quick_search(self, query: str, query_domains: list[str] = None, aggregated_summary: bool = False) -> list[Any] | str:
        """执行一个轻量搜索，而不走完整研究链路。

        参数说明：
            query:
                要搜索的问题。
            query_domains:
                域名限制；如果传入，只在这些域名范围内检索。
            aggregated_summary:
                是否把搜索结果进一步汇总成一段摘要。
                - False: 直接返回原始搜索结果列表
                - True: 额外调用模型，把搜索结果整理成摘要文本

        返回值：
            list[Any] | str:
                可能返回原始搜索结果列表，也可能返回模型汇总后的字符串。

        这个方法适合“快速问一下外部信息”的场景，
        不适合替代完整的 `conduct_research()`。
        """
        search_results = await get_search_results(query, self.retrievers[0], query_domains=query_domains)

        if not aggregated_summary:
            return search_results

        # 如果调用方要求聚合摘要，就先把原始搜索结果格式化成一段 context，
        # 再交给模型统一概括。
        context = ""
        for i, result in enumerate(search_results, 1):
            context += f"[{i}] {result.get('title', '')}: {result.get('content', '')} ({result.get('url', '')})\n\n"

        prompt = self.prompt_family.generate_quick_summary_prompt(query, context)

        summary = await create_chat_completion(
            model=self.cfg.smart_llm_model,
            messages=[{"role": "user", "content": prompt}],
            llm_provider=self.cfg.smart_llm_provider,
            max_tokens=self.cfg.smart_token_limit,
            llm_kwargs=self.cfg.llm_kwargs,
            cost_callback=self.add_costs
        )

        return summary

    async def get_subtopics(self):
        """为当前问题生成子主题。

        返回值：
            list: 自动规划出来的子主题列表。
        """
        return await self.report_generator.get_subtopics()

    async def get_draft_section_titles(self, current_subtopic: str) -> list[str]:
        """Generate draft section titles for a subtopic.

        Args:
            current_subtopic: The subtopic to generate sections for.

        Returns:
            List of section title strings.
        """
        return await self.report_generator.get_draft_section_titles(current_subtopic)

    async def get_similar_written_contents_by_draft_section_titles(
        self,
        current_subtopic: str,
        draft_section_titles: list[str],
        written_contents: list[dict],
        max_results: int = 10
    ) -> list[str]:
        """Find similar previously written contents based on section titles.

        Args:
            current_subtopic: The current subtopic being written.
            draft_section_titles: List of draft section titles.
            written_contents: Previously written content to search through.
            max_results: Maximum number of results to return.

        Returns:
            List of similar content strings.
        """
        return await self.context_manager.get_similar_written_contents_by_draft_section_titles(
            current_subtopic,
            draft_section_titles,
            written_contents,
            max_results
        )

    # Utility methods
    def get_research_images(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Get the top research images collected during research.

        Args:
            top_k: Maximum number of images to return.

        Returns:
            List of image dictionaries.
        """
        return self.research_images[:top_k]

    def add_research_images(self, images: list[dict[str, Any]]) -> None:
        """Add images to the research image collection.

        Args:
            images: List of image dictionaries to add.
        """
        self.research_images.extend(images)

    def get_research_sources(self) -> list[dict[str, Any]]:
        """Get all research sources collected during research.

        Returns:
            List of source dictionaries containing title, content, and images.
        """
        return self.research_sources

    def add_research_sources(self, sources: list[dict[str, Any]]) -> None:
        """Add sources to the research source collection.

        Args:
            sources: List of source dictionaries to add.
        """
        self.research_sources.extend(sources)

    def add_references(self, report_markdown: str, visited_urls: set) -> str:
        """Add reference section to a markdown report.

        Args:
            report_markdown: The markdown report text.
            visited_urls: Set of URLs to include as references.

        Returns:
            The report with references appended.
        """
        return add_references(report_markdown, visited_urls)

    def extract_headers(self, markdown_text: str) -> list[dict]:
        """Extract headers from markdown text.

        Args:
            markdown_text: The markdown text to parse.

        Returns:
            List of header dictionaries.
        """
        return extract_headers(markdown_text)

    def extract_sections(self, markdown_text: str) -> list[dict]:
        """Extract sections from markdown text.

        Args:
            markdown_text: The markdown text to parse.

        Returns:
            List of section dictionaries.
        """
        return extract_sections(markdown_text)

    def table_of_contents(self, markdown_text: str) -> str:
        """Generate a table of contents for markdown text.

        Args:
            markdown_text: The markdown text to generate TOC for.

        Returns:
            The table of contents as markdown string.
        """
        return table_of_contents(markdown_text)

    def get_source_urls(self) -> list:
        """Get all visited source URLs.

        Returns:
            List of visited URL strings.
        """
        return list(self.visited_urls)

    def get_research_context(self) -> list:
        """Get the accumulated research context.

        Returns:
            List of context items collected during research.
        """
        return self.context

    def get_costs(self) -> float:
        """Get the total accumulated API costs.

        Returns:
            Total cost in USD.
        """
        return self.research_costs

    def get_step_costs(self) -> dict[str, float]:
        """Get a breakdown of API costs per research step.

        Returns:
            Dictionary mapping step names to their costs in USD.
        """
        return dict(self.step_costs)

    def set_verbose(self, verbose: bool) -> None:
        """Set the verbose output mode.

        Args:
            verbose: Whether to enable verbose output.
        """
        self.verbose = verbose

    def add_costs(self, cost: float) -> None:
        """Add to the accumulated API costs.

        The cost is attributed to the current step set via ``_current_step``.

        Args:
            cost: Cost amount to add in USD.

        Raises:
            ValueError: If cost is not a number.
        """
        if not isinstance(cost, (float, int)):
            raise ValueError("Cost must be an integer or float")
        self.research_costs += cost
        step = self._current_step
        self.step_costs[step] = self.step_costs.get(step, 0.0) + cost
        if self.log_handler:
            self._log_event("research", step="cost_update", details={
                "cost": cost,
                "total_cost": self.research_costs,
                "step_name": step,
            })
