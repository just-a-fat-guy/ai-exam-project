"""检索器工厂与选择工具。

这个文件本身不负责“执行搜索”，它只负责两件事：

1. 根据字符串名称找到对应的 retriever 类
2. 根据 headers / config / 默认值，决定当前应启用哪些 retriever

也就是说，它是研究能力层里一个很典型的“装配层”文件。
"""


def get_retriever(retriever: str):
    """根据名称返回对应的 retriever 类。

    参数说明：
        retriever:
            检索器名称字符串，例如 `google`、`tavily`、`duckduckgo`、`mcp`。

    返回值：
        type | None:
            找到时返回对应的 retriever 类；找不到时返回 `None`。

    这里返回的是“类”，不是已经构造好的实例。
    真正实例化通常发生在研究流程更上层的位置。
    """
    match retriever:
        case "google":
            from gpt_researcher.retrievers import GoogleSearch

            return GoogleSearch
        case "searx":
            from gpt_researcher.retrievers import SearxSearch

            return SearxSearch
        case "searchapi":
            from gpt_researcher.retrievers import SearchApiSearch

            return SearchApiSearch
        case "serpapi":
            from gpt_researcher.retrievers import SerpApiSearch

            return SerpApiSearch
        case "serper":
            from gpt_researcher.retrievers import SerperSearch

            return SerperSearch
        case "duckduckgo":
            from gpt_researcher.retrievers import Duckduckgo

            return Duckduckgo
        case "bing":
            from gpt_researcher.retrievers import BingSearch

            return BingSearch
        case "bocha":
            from gpt_researcher.retrievers import BoChaSearch

            return BoChaSearch
        case "arxiv":
            from gpt_researcher.retrievers import ArxivSearch

            return ArxivSearch
        case "tavily":
            from gpt_researcher.retrievers import TavilySearch

            return TavilySearch
        case "exa":
            from gpt_researcher.retrievers import ExaSearch

            return ExaSearch
        case "semantic_scholar":
            from gpt_researcher.retrievers import SemanticScholarSearch

            return SemanticScholarSearch
        case "pubmed_central":
            from gpt_researcher.retrievers import PubMedCentralSearch

            return PubMedCentralSearch
        case "custom":
            from gpt_researcher.retrievers import CustomRetriever

            return CustomRetriever
        case "mcp":
            from gpt_researcher.retrievers import MCPRetriever

            return MCPRetriever

        case _:
            return None


def get_retrievers(headers: dict[str, str], cfg):
    """确定当前研究任务应该启用哪些 retriever。

    参数说明：
        headers:
            请求头或上层传入的运行时参数。这里允许调用方临时覆盖 retriever 配置。
        cfg:
            配置对象。若 headers 没指定，就从配置文件或环境变量里取。

    返回值：
        list:
            retriever 类列表，而不是字符串列表。

    决策优先级：
        1. headers 里的 `retrievers`
        2. headers 里的 `retriever`
        3. cfg.retrievers
        4. cfg.retriever
        5. 默认 retriever
    """
    # 优先看 headers 里的多检索器配置。
    if headers.get("retrievers"):
        retrievers = headers.get("retrievers").split(",")
    # 再看 headers 里的单检索器配置。
    elif headers.get("retriever"):
        retrievers = [headers.get("retriever")]
    # headers 没配置时，再看配置对象里的多检索器设置。
    elif cfg.retrievers:
        # 兼容 cfg.retrievers 是字符串或列表两种情况。
        if isinstance(cfg.retrievers, str):
            retrievers = cfg.retrievers.split(",")
        else:
            retrievers = cfg.retrievers
        retrievers = [r.strip() for r in retrievers]
    # 再退回到配置对象里的单检索器设置。
    elif cfg.retriever:
        retrievers = [cfg.retriever]
    # 最后兜底默认值。
    else:
        retrievers = [get_default_retriever().__name__]

    # 把名称列表转换成类列表。
    # 如果某个名称无效，就自动回退到默认 retriever，避免整个流程直接崩掉。
    retriever_classes = [get_retriever(r) or get_default_retriever() for r in retrievers]
    
    return retriever_classes


def get_default_retriever():
    """返回默认检索器类。

    当前默认值是 `TavilySearch`。
    这个默认选择反映的是仓库作者的原始假设，并不一定适合你本地所有场景。
    """
    from gpt_researcher.retrievers import TavilySearch

    return TavilySearch
