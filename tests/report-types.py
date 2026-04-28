"""Day 2/Day 3 学习时最适合先读的最小闭环测试。

这个文件的价值不在于测试逻辑有多复杂，而在于它把 GPT Researcher
最核心的一条主链路压缩到了几行代码里：

1. 创建 `GPTResearcher`
2. 先执行 `conduct_research()`
3. 再执行 `write_report()`
4. 最后对结果和访问来源做断言

如果你刚开始读项目源码，优先看懂这个文件，会比直接扎进具体
retriever / scraper / prompt 实现更容易建立整体认知。
"""

import pytest
from unittest.mock import AsyncMock
from gpt_researcher.agent import GPTResearcher
from backend.server.server_utils import CustomLogsHandler

# 这里一次覆盖两种报告类型。
# 这样同一套最小主链路就能验证：
# 1. 常规研究报告是否可跑通
# 2. 子主题报告是否也能复用同样的主入口
report_types = ["research_report", "subtopic_report"]

# 统一使用一个固定问题，让测试结果更稳定。
# 这个问题本身不重要，重要的是它能在 GitHub 域名下搜到足够结果。
query = "what is gpt-researcher"


@pytest.mark.asyncio
@pytest.mark.parametrize("report_type", report_types)
async def test_gpt_researcher(report_type):
    """验证 GPTResearcher 的最小闭环是否成立。

    参数说明：
        report_type:
            由 `pytest.mark.parametrize` 注入。
            每次测试运行时会分别取 `research_report` 与 `subtopic_report`，
            用来验证同一个主入口是否能支持不同报告类型。

    这段测试最值得学习的不是断言本身，而是调用顺序：

    1. 先构造 `GPTResearcher`
    2. 先研究 `conduct_research()`
    3. 后写作 `write_report()`

    这也是整个项目最核心的执行顺序。
    """
    # 用 AsyncMock 模拟 WebSocket，避免测试时真的依赖前端连接。
    # 这样既能保留“流式日志输出”的调用路径，又不需要启动服务器。
    mock_websocket = AsyncMock()

    # CustomLogsHandler 是测试环境下的日志桥接器。
    # GPTResearcher 在研究和写报告过程中产生的日志，会先发给它，
    # 再由它转发到 mock_websocket。
    custom_logs_handler = CustomLogsHandler(mock_websocket, query)

    # 创建主入口对象。
    #
    # 参数说明：
    # - query: 用户要研究的问题
    # - query_domains: 限定只能在 github.com 下检索，便于控制结果范围
    # - report_type: 本次要生成的报告类型
    # - websocket: 接收中间日志输出的对象
    researcher = GPTResearcher(
        query=query,
        query_domains=["github.com"],
        report_type=report_type,
        websocket=custom_logs_handler,
    )

    # 第一步：做研究。
    # 这一阶段会完成检索、抓取、上下文整理等动作，最终把结果放进
    # `researcher.context` 里，供下一步写报告使用。
    await researcher.conduct_research()

    # 第二步：写报告。
    # 这一阶段会读取上一步已经整理好的 context，然后调用模型生成最终文本。
    report = await researcher.write_report()

    print(researcher.visited_urls)
    print(report)

    # 断言 1：报告文本里至少应当包含问题中的核心关键词。
    # 这是一个很粗粒度但足够实用的 smoke test。
    assert "gpt-researcher" in report

    # 断言 2：访问过的 URL 至少有一个来自 github.com。
    # 这个断言验证 `query_domains=["github.com"]` 确实影响了检索来源。
    matching_urls = [
        url for url in researcher.visited_urls if url.startswith("https://github.com")
    ]
    assert len(matching_urls) > 0


if __name__ == "__main__":
    # 允许直接用 `python tests/report-types.py` 方式单独运行这个测试文件。
    pytest.main()
