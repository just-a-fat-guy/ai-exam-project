import json_repair

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts
from ..utils.llm import create_chat_completion
from ..prompts import PromptFamily
from typing import Any, List, Dict
from ..config import Config
import logging

logger = logging.getLogger(__name__)

async def get_search_results(query: str, retriever: Any, query_domains: List[str] = None, researcher=None) -> List[Dict[str, Any]]:
    """调用指定 retriever，拿到某个 query 的原始搜索结果。

    参数说明：
        query:
            当前搜索问题。
        retriever:
            检索器类，而不是实例。这里会在函数内部负责实例化。
        query_domains:
            域名限制列表；如果提供，搜索会限制在这些域名范围内。
        researcher:
            上层 `GPTResearcher` 实例。普通 retriever 不一定需要它，
            但 MCP retriever 往往依赖它拿到 cfg / websocket / mcp_configs 等上下文。

    返回值：
        List[Dict[str, Any]]:
            原始搜索结果列表。后续研究编排会基于这些结果继续拆子查询或抓正文。
    """
    # MCP retriever 与普通 retriever 的初始化签名不同，
    # 因此这里做一层分流。
    if "mcpretriever" in retriever.__name__.lower():
        search_retriever = retriever(
            query, 
            query_domains=query_domains,
            researcher=researcher
        )
    else:
        search_retriever = retriever(query, query_domains=query_domains)
    
    # 这里只负责返回“原始搜索结果”，不负责抓网页和压缩上下文。
    return search_retriever.search()

async def generate_sub_queries(
    query: str,
    parent_query: str,
    report_type: str,
    context: List[Dict[str, Any]],
    cfg: Config,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """基于问题和初始搜索结果，让模型生成子查询列表。

    参数说明：
        query:
            当前问题。
        parent_query:
            父问题。对于 subtopic / detailed report 场景，父问题可以帮助模型
            更准确地理解“当前子问题属于哪个总任务”。
        report_type:
            报告类型，不同类型会影响 query prompt 的组织方式。
        context:
            初始搜索结果上下文。这里通常不是完整正文，而是粗粒度搜索结果摘要。
        cfg:
            配置对象，里面包含 strategic/smart LLM 的模型与 token 配置。
        cost_callback:
            成本统计回调。
        prompt_family:
            prompt family，用来生成“拆子查询”的提示词模板。

    返回值：
        List[str]:
            模型输出的子查询列表。

    这个函数的核心意义：
        不是直接拿初始搜索结果去写报告，
        而是先让模型根据这些结果规划下一步应该研究哪些子问题。
    """
    gen_queries_prompt = prompt_family.generate_search_queries_prompt(
        query,
        parent_query,
        report_type,
        max_iterations=cfg.max_iterations or 3,
        context=context,
    )

    try:
        # 第一优先级：使用 strategic LLM。
        # 这类模型通常更适合做“研究规划”和“任务拆分”。
        response = await create_chat_completion(
            model=cfg.strategic_llm_model,
            messages=[{"role": "user", "content": gen_queries_prompt}],
            llm_provider=cfg.strategic_llm_provider,
            max_tokens=None,
            llm_kwargs=cfg.llm_kwargs,
            reasoning_effort=ReasoningEfforts.Medium.value,
            cost_callback=cost_callback,
            **kwargs
        )
    except Exception as e:
        # 有些 provider 在 max_tokens=None 下不稳定，因此这里先做一次参数降级重试。
        logger.warning(f"Error with strategic LLM: {e}. Retrying with max_tokens={cfg.strategic_token_limit}.")
        logger.warning(f"See https://github.com/assafelovic/gpt-researcher/issues/1022")
        try:
            response = await create_chat_completion(
                model=cfg.strategic_llm_model,
                messages=[{"role": "user", "content": gen_queries_prompt}],
                max_tokens=cfg.strategic_token_limit,
                llm_provider=cfg.strategic_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
            logger.warning(f"Retrying with max_tokens={cfg.strategic_token_limit} successful.")
        except Exception as e:
            # strategic LLM 两轮都失败时，再回退到 smart LLM。
            # 这属于“能力降级但不中断流程”的设计。
            logger.warning(f"Retrying with max_tokens={cfg.strategic_token_limit} failed.")
            logger.warning(f"Error with strategic LLM: {e}. Falling back to smart LLM.")
            response = await create_chat_completion(
                model=cfg.smart_llm_model,
                messages=[{"role": "user", "content": gen_queries_prompt}],
                temperature=cfg.temperature,
                max_tokens=cfg.smart_token_limit,
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )

    # 模型输出的 JSON 可能并不完全合法，因此这里用 json_repair 做容错解析。
    return json_repair.loads(response)

async def plan_research_outline(
    query: str,
    search_results: List[Dict[str, Any]],
    agent_role_prompt: str,
    cfg: Config,
    parent_query: str,
    report_type: str,
    cost_callback: callable = None,
    retriever_names: List[str] = None,
    **kwargs
) -> List[str]:
    """规划研究大纲，本质上就是生成“后续要研究哪些子查询”。

    参数说明：
        query:
            原始问题。
        search_results:
            初始搜索结果。
        agent_role_prompt:
            当前 agent 角色提示词。这个参数目前保留在接口里，便于未来扩展，
            当前函数本体不直接使用它。
        cfg:
            配置对象。
        parent_query:
            父问题。
        report_type:
            报告类型。
        cost_callback:
            成本统计回调。
        retriever_names:
            当前启用的 retriever 名称列表。

    返回值：
        List[str]:
            规划好的子查询列表。

    这里最关键的特殊处理是 MCP：
        - 如果只有 MCP 一个检索器，可以直接跳过子查询扩展
        - 如果 MCP 与其他检索器混用，则仍然需要给普通检索器生成子查询
    """
    # 调用方没传时，统一变成空列表，避免后面判断出错。
    if retriever_names is None:
        retriever_names = []
    
    # 如果当前配置中包含 MCP，需要先判断它是不是唯一检索器。
    if retriever_names and ("mcp" in retriever_names or "MCPRetriever" in retriever_names):
        mcp_only = (len(retriever_names) == 1 and 
                   ("mcp" in retriever_names or "MCPRetriever" in retriever_names))
        
        if mcp_only:
            # 纯 MCP 模式下，很多情况下直接把原问题交给 MCP 就够了，
            # 没必要再额外拆很多子查询。
            logger.info("Using MCP retriever only - skipping sub-query generation")
            return [query]
        else:
            # MCP 和普通检索器混用时，仍然要给普通检索器生成子查询。
            logger.info("Using MCP with other retrievers - generating sub-queries for non-MCP retrievers")

    # 标准路径：调用 generate_sub_queries，让模型给出研究大纲。
    sub_queries = await generate_sub_queries(
        query,
        parent_query,
        report_type,
        search_results,
        cfg,
        cost_callback,
        **kwargs
    )

    return sub_queries
