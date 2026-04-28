# Day 2：主执行链路与系统学习路线

## 今日目标

Day 1 你已经把项目跑起来了。  
Day 2 不再以“怎么启动”为主，而是开始建立源码层面的第一张完整地图。

说明：下面出现的核心文件名，我已经改成了可点击的 Markdown 相对链接。  
在 IDE 里阅读这个文档时，优先直接点链接跳转，不要手动全局搜索。

今天只做三件事：

1. 建立整个项目的系统学习路线。
2. 读懂这个项目最核心的一条主执行链路。
3. 明确后面每一部分代码应该按什么顺序继续深入。

今天仍然不要一上来就钻细节实现。  
先把“入口 -> 编排 -> 研究 -> 写报告 -> 输出”的骨架建立起来。

## 先给出整体学习路线

如果你想系统性地学这个项目，我建议按下面这条路线走。

### 第一阶段：先建立骨架，再进细节

1. Day 1：项目启动与第一次使用
2. Day 2：主执行链路
3. Day 3：研究流程
4. Day 4：抓取、上下文压缩与 embedding
5. Day 5：报告生成与 prompt
6. Day 6：配置系统与可扩展点
7. Day 7：后端接口、前端交互、聊天与 MCP

### 第二阶段：再看进阶能力

1. `detailed_report`
2. `deep_research`
3. `multi_agents`
4. 自定义 retriever / 自定义 provider / 自定义 prompt family

### 第三阶段：最后回头做代码级归纳

1. 哪些模块是稳定核心
2. 哪些模块是扩展层
3. 哪些地方有明显历史包袱
4. 哪些地方适合你以后自己改造

## 为什么 Day 2 先学主执行链路

因为这个项目不是一个“很多独立功能的集合”，而是一条很明确的工作流：

```text
入口 -> 构造 GPTResearcher -> conduct_research() -> write_report() -> 输出文件/页面结果
```

如果这条链你没有看明白，那么你后面去看：

1. retriever
2. scraper
3. embedding
4. prompt
5. websocket

都会变成碎片知识。

所以 Day 2 的任务不是“看懂所有代码”，而是“先看懂主干”。

## 今天最先要建立的心智模型

先记住这句：

```text
用例入口 -> GPTResearcher -> ResearchConductor -> 上下文 -> ReportGenerator -> 文件/前端输出
```

你今天读源码时，只要不断问自己一句：

```text
现在这一步是在主链路里的哪一段？
```

## Day 2 推荐阅读顺序

今天建议严格按这个顺序读，不要跳。

### 第 1 站：最小闭环入口

先读：

1. [tests/report-types.py](../tests/report-types.py)
2. [cli.py](../cli.py)

你要观察的是：

1. 这个项目最小怎么创建 `GPTResearcher`
2. 外部到底调用了哪两个核心方法
3. 这两个方法的顺序是不是固定的

你会很快看到一个最关键的事实：

```python
await researcher.conduct_research()
report = await researcher.write_report() 
```

这基本就是整个项目主干的缩影。

### 第 2 站：主类 GPTResearcher

接着读：

1. [gpt_researcher/agent.py](../gpt_researcher/agent.py)

重点看这三个位置：

1. `class GPTResearcher`
2. `conduct_research()`
3. `write_report()`

你要搞清楚：

1. 这个类在初始化时持有哪些核心状态
2. `conduct_research()` 主要负责什么
3. `write_report()` 主要负责什么
4. 哪些能力是委托给别的类去做的

今天的一个关键收获应该是：

`GPTResearcher` 自己不是“所有事情都做”，它更像一个总编排器。

### 第 3 站：研究流程编排器

然后读：

1. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)

重点看：

1. `class ResearchConductor`
2. `plan_research()`
3. `conduct_research()`

你要理解：

1. 主问题是如何被拆成子查询的
2. 检索器什么时候开始工作
3. 搜索结果如何一步步转成 `context`

这一步会让你真正理解：

这个项目不是“直接让模型写答案”，而是先做一轮研究编排。

### 第 4 站：报告生成器

最后读：

1. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)
2. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)

你要理解：

1. `context` 是怎么进入写作阶段的
2. prompt 是在哪里真正拼出来的
3. 写出来的报告最后为什么会变成 `md/docx/pdf`

到这一步，你就已经拥有了“这个项目主链路”的第一版全景图。

## 今天建议重点看的文件

如果只列 Day 2 必看文件，就是这 6 个：

1. [tests/report-types.py](../tests/report-types.py)
2. [cli.py](../cli.py)
3. [gpt_researcher/agent.py](../gpt_researcher/agent.py)
4. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)
5. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)
6. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)

## 原始项目的模块地图

如果你想“完整学习原始 GPT Researcher”，建议先把整个仓库粗分成下面几层。

### 1. 入口层

这一层负责把用户请求送进主工作流：

1. [tests/report-types.py](../tests/report-types.py)
2. [cli.py](../cli.py)
3. [backend/server/server_utils.py](../backend/server/server_utils.py)
4. [backend/server/websocket_manager.py](../backend/server/websocket_manager.py)

### 2. 核心编排层

这一层是整个项目的主干：

1. [gpt_researcher/agent.py](../gpt_researcher/agent.py)
2. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)
3. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)

### 3. 研究能力层

这一层负责“怎么找资料、怎么整理资料”：

1. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)
2. [gpt_researcher/actions/retriever.py](../gpt_researcher/actions/retriever.py)
3. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
4. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
5. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)

### 4. 生成能力层

这一层负责“怎么把 context 变成报告”：

1. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)
3. [gpt_researcher/utils/llm.py](../gpt_researcher/utils/llm.py)

### 5. 基础设施层

这一层负责模型、配置、导出、日志等底层支撑：

1. [gpt_researcher/config/config.py](../gpt_researcher/config/config.py)
2. [gpt_researcher/memory/embeddings.py](../gpt_researcher/memory/embeddings.py)
3. [backend/utils.py](../backend/utils.py)
4. [backend/chat/chat.py](../backend/chat/chat.py)

### 6. 进阶能力层

这一层先知道名字就够了，Day 2 不展开：

1. [backend/report_type/detailed_report/detailed_report.py](../backend/report_type/detailed_report/detailed_report.py)
2. [backend/report_type/deep_research](../backend/report_type/deep_research)
3. [multi_agents](../multi_agents)
4. [gpt_researcher/mcp](../gpt_researcher/mcp)

你今天最重要的判断是：

```text
Day 2 先学入口层和核心编排层，不先学研究能力层的细节实现。
```

## Day 2 核心代码清单

下面这几段代码，是你今天必须能看懂的“主干节点”。

### 核心 1：最小入口样例

位置：

1. [tests/report-types.py](../tests/report-types.py)

最小主链代码：

```python
researcher = GPTResearcher(
    query=query,
    query_domains=["github.com"],
    report_type=report_type,
    websocket=custom_logs_handler,
)

await researcher.conduct_research()
report = await researcher.write_report()
```

中文注释：

```python
researcher = GPTResearcher(
    query=query,                      # 用户真正想研究的问题
    query_domains=["github.com"],    # 限制检索范围，只搜指定域名
    report_type=report_type,         # 决定最终报告类型
    websocket=custom_logs_handler,   # 把中间日志流式发到前端/测试桩
)

await researcher.conduct_research()  # 第一步：先做资料检索、抓取、整理
report = await researcher.write_report()  # 第二步：再基于 context 写最终报告
```

这段代码的重要性在于，它把整个项目压缩成了两个核心动作：

1. `conduct_research()`
2. `write_report()`

### 核心 2：GPTResearcher 是总编排器

位置：

1. [gpt_researcher/agent.py](../gpt_researcher/agent.py)

你今天先重点关注下面这些初始化参数：

```python
def __init__(
    self,
    query: str,
    report_type: str = ReportType.ResearchReport.value,
    report_source: str = ReportSource.Web.value,
    tone: Tone = Tone.Objective,
    query_domains: list[str] | None = None,
    websocket=None,
    ...
):
```

中文注释：

```python
def __init__(
    self,
    query: str,                      # 研究主题
    report_type: str = ...,          # 生成哪种报告
    report_source: str = ...,        # 数据来源：web / local / hybrid
    tone: Tone = ...,                # 报告语气
    query_domains: list[str] | None = None,  # 检索域名限制
    websocket=None,                  # 用于向前端推送中间日志与结果
    ...
):
```

你要从这里看出一个事实：

`GPTResearcher` 不是单一功能类，而是整个系统对外暴露的统一入口对象。

### 核心 3：研究阶段主入口

位置：

1. [gpt_researcher/agent.py:331](../gpt_researcher/agent.py#L331)

核心代码：

```python
if not (self.agent and self.role):
    self.agent, self.role = await choose_agent(...)

self.context = await self.research_conductor.conduct_research()
```

中文注释：

```python
if not (self.agent and self.role):
    self.agent, self.role = await choose_agent(...)
    # 如果还没有确定“研究员角色”，先让模型决定这次任务该用什么研究身份

self.context = await self.research_conductor.conduct_research()
# 真正进入研究阶段
# 这里并不是自己直接去搜，而是把任务交给 ResearchConductor
# 最终得到的是后续写报告要用的 context
```

这一段最重要的理解是：

1. [gpt_researcher/agent.py](../gpt_researcher/agent.py) 负责调度
2. 真正的研究细节不写在 [gpt_researcher/agent.py](../gpt_researcher/agent.py)
3. `context` 是研究阶段最重要的产物

### 核心 4：研究编排器怎么拆任务

位置：

1. [gpt_researcher/skills/researcher.py:48](../gpt_researcher/skills/researcher.py#L48)
2. [gpt_researcher/skills/researcher.py:89](../gpt_researcher/skills/researcher.py#L89)

核心代码：

```python
search_results = await get_search_results(query, self.researcher.retrievers[0], query_domains, researcher=self.researcher)
outline = await plan_research_outline(...)
```

中文注释：

```python
search_results = await get_search_results(
    query,
    self.researcher.retrievers[0],
    query_domains,
    researcher=self.researcher,
)
# 先用当前配置的检索器拿一批初始搜索结果

outline = await plan_research_outline(...)
# 再把“用户问题 + 初始搜索结果 + 当前角色”交给模型
# 让模型规划出一组更适合后续深入研究的子查询
```

这一步体现了 GPT Researcher 的核心思路：

```text
不是直接搜一次就写，而是先用搜索结果帮助模型规划研究路径。
```

### 核心 5：研究编排器如何并发处理子查询

位置：

1. [gpt_researcher/skills/researcher.py:242](../gpt_researcher/skills/researcher.py#L242)

核心代码：

```python
sub_queries = await self.plan_research(query)
if self.researcher.report_type != "subtopic_report":
    sub_queries.append(query)

context = await asyncio.gather(
    *[
        self._process_sub_query_with_vectorstore(sub_query, filter)
        for sub_query in sub_queries
    ]
)
```

中文注释：

```python
sub_queries = await self.plan_research(query)
# 先拿到研究大纲拆出的子查询

if self.researcher.report_type != "subtopic_report":
    sub_queries.append(query)
# 如果不是特殊子主题报告，就把原始问题也一起纳入研究

context = await asyncio.gather(
    *[
        self._process_sub_query_with_vectorstore(sub_query, filter)
        for sub_query in sub_queries
    ]
)
# 并发处理所有子查询
# 每个子查询内部都会经历：检索 -> 抓取 -> 相似内容筛选 -> 拼成 context
```

你今天应该意识到：

这个项目“像 agent”的地方，主要不在于能聊天，而在于它把一个大问题拆成多个研究子任务并发执行。

### 核心 6：写报告前的参数组装

位置：

1. [gpt_researcher/skills/writer.py:49](../gpt_researcher/skills/writer.py#L49)

核心代码：

```python
context = ext_context or self.researcher.context
report_params = self.research_params.copy()
report_params["context"] = context
report_params["custom_prompt"] = custom_prompt

report = await generate_report(**report_params, **self.researcher.kwargs)
```

中文注释：

```python
context = ext_context or self.researcher.context
# 优先用外部传入的 context；如果没有，就用研究阶段产出的内部 context

report_params = self.research_params.copy()
# 先复制一份基础写作参数，避免直接改原对象

report_params["context"] = context
report_params["custom_prompt"] = custom_prompt
# 把上下文和自定义 prompt 都装进写作参数

report = await generate_report(**report_params, **self.researcher.kwargs)
# 真正进入“向模型写报告”的动作
```

[gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py) 的职责不是写 prompt，而是：

1. 整理写作阶段需要的参数
2. 管理写作阶段日志
3. 调用真正的报告生成函数

### 核心 7：最终报告是怎么调用大模型的

位置：

1. [gpt_researcher/actions/report_generation.py:216](../gpt_researcher/actions/report_generation.py#L216)

核心代码：

```python
generate_prompt = get_prompt_by_report_type(report_type, prompt_family)

content = generate_prompt(
    query,
    context,
    report_source,
    report_format=cfg.report_format,
    tone=tone,
    total_words=cfg.total_words,
    language=cfg.language,
)

report = await create_chat_completion(
    model=cfg.smart_llm_model,
    messages=messages,
    llm_provider=cfg.smart_llm_provider,
    ...
)
```

中文注释：

```python
generate_prompt = get_prompt_by_report_type(report_type, prompt_family)
# 先根据报告类型，选择对应的 prompt 模板函数

content = generate_prompt(...)
# 再把 query、context、语言、格式、语气等参数拼成最终提示词

report = await create_chat_completion(...)
# 最后通过统一的 LLM 调用工具，真正请求模型生成报告
```

这一段很关键，因为它告诉你：

1. prompt 选择发生在 action 层
2. 大模型调用也收束在 action / util 层
3. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py) 和 [gpt_researcher/agent.py](../gpt_researcher/agent.py) 都不是最终调用模型的最低层

## 补充：浏览器入口是怎么接到同一条主链路的

如果你不是从测试和 CLI 看代码，而是从浏览器发起任务，那么入口会多一层后端转发。

### 浏览器入口 1：收到 `start` 指令

位置：

1. [backend/server/server_utils.py:126](../backend/server/server_utils.py#L126)

核心代码：

```python
report = await manager.start_streaming(
    task,
    report_type,
    report_source,
    ...
)
```

中文注释：

```python
report = await manager.start_streaming(...)
# 前端通过 WebSocket 发来的任务，先在 server 层解包
# 再统一转交给 websocket manager
```

### 浏览器入口 2：真正创建报告对象

位置：

1. [backend/server/websocket_manager.py:100](../backend/server/websocket_manager.py#L100)

核心代码：

```python
report = await run_agent(...)

researcher = BasicReport(...)
report = await researcher.run()
```

中文注释：

```python
report = await run_agent(...)
# 先进入统一的 agent 运行入口

researcher = BasicReport(...)
# 根据 report_type 选择具体的报告对象

report = await researcher.run()
# 最终仍然会在内部创建 GPTResearcher，然后走相同主链
```

这说明：

```text
测试入口、CLI 入口、浏览器入口，最后都会汇聚到 GPTResearcher 主链路。
```

## 今天每个文件应该怎么看

下面不是“文件介绍”，而是你真正阅读时应该关注的问题。

### 1. [tests/report-types.py](../tests/report-types.py)

阅读目标：

1. 找到最小调用样例
2. 看看 `GPTResearcher` 初始化需要哪些参数
3. 看看测试如何验证报告结果

你读完之后应该能回答：

1. `query_domains` 是怎么传进去的
2. `report_type` 不同会影响什么
3. 测试为什么要先 `conduct_research()` 再 `write_report()`

### 2. [cli.py](../cli.py)

阅读目标：

1. 看命令行参数是怎么映射到 `GPTResearcher` 参数的
2. 看报告生成后如何写到 `outputs/`
3. 看 CLI 和前端调用在本质上是不是同一条主链路

你要注意：

CLI 不是另一个系统。  
它只是绕开前端，直接调用同一个核心类。

### 3. [gpt_researcher/agent.py](../gpt_researcher/agent.py)

阅读目标：

1. 搞清楚 `GPTResearcher` 的职责边界
2. 找到它和 `Config`、`ResearchConductor`、`writer` 的关系
3. 理解它为什么是整个项目的中枢类

你今天读这份文件时，不要试图看懂所有属性。  
只需要抓住下面三类信息：

1. 输入参数
2. 关键依赖对象
3. 两个核心方法：`conduct_research()`、`write_report()`

### 4. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)

阅读目标：

1. 研究任务是怎么启动的
2. 子查询是怎么规划出来的
3. 检索、抓取、上下文整理在这里是怎么串联的

这一层你要重点看“流程”，不要卡在“某个 retriever 的具体实现”。

### 5. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)

阅读目标：

1. 写报告前它做了哪些准备
2. 它是怎么把上下文交给 `generate_report()` 的
3. 项目如何向前端流式输出“正在写报告”

今天你应该意识到：

[gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py) 不是纯模板代码，它是“报告写作阶段的控制层”。

### 6. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)

阅读目标：

1. 最终 prompt 是怎么组出来的
2. LLM 调用发生在哪里
3. 失败时有哪些 fallback

这份文件会帮你理解：

真正“向模型发请求”的代码，往往在 action / util 层，而不是都堆在 [gpt_researcher/agent.py](../gpt_researcher/agent.py) 里。

## 今天先不要深挖的内容

为了避免 Day 2 被细节拖住，下面这些今天先不要深挖：

1. 各种 retriever 的具体 provider 实现
2. scraper 的具体抓取细节
3. embedding 的具体数学原理
4. MCP 的 server 配置细节
5. `deep_research` 和 `multi_agents`
6. Next.js 前端组件细节

今天的目标不是“读很多”，而是“把主干读直”。

## Day 2 推荐阅读动作

不要只看文件。今天建议你边读边做下面这些动作。

### 动作 1：自己手动画一条主链路

例如：

1. [tests/report-types.py](../tests/report-types.py)
2. `-> GPTResearcher(...)`
3. `-> conduct_research()`
4. `-> ResearchConductor.conduct_research()`
5. `-> context`
6. `-> write_report()`
7. `-> writer.generate_report()`

这张图不需要漂亮，但一定要自己画。

### 动作 2：记录“谁负责什么”

建议你边读边整理一张三列表：

1. 文件
2. 核心类 / 函数
3. 职责

例如：

1. [gpt_researcher/agent.py](../gpt_researcher/agent.py)：总编排
2. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)：研究流程编排
3. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)：报告写作控制
4. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)：最终 LLM 报告生成

### 动作 3：只追主链，不追分叉

一旦你读到某个函数里调用了很多别的函数，不要全部跳进去。  
先问：

```text
这个调用是不是主链关键节点？
```

如果不是，先记下来，Day 3 或 Day 4 再回来看。

## Day 2 读完后你应该能回答的问题

如果今天真的读明白了，你至少应该能回答下面这些问题：

1. `GPTResearcher` 是主类，还是只是一个 facade？
2. 为什么主流程要拆成 `conduct_research()` 和 `write_report()` 两步？
3. 子查询规划发生在哪一层？
4. 搜索结果是在哪里转成上下文的？
5. 报告真正向 LLM 发请求是在哪一层？
6. CLI、测试、前端这几个入口，最后是不是都会收敛到同一条主链路？

## Day 2 的最小产出

今天结束时，你至少应该自己写出这三条：

### 1. 一句话主链路

```text
入口创建 GPTResearcher，先 conduct_research 拿 context，再 write_report 生成最终报告。
```

### 2. 一句话职责分工

```text
gpt_researcher/agent.py 负责编排，gpt_researcher/skills/researcher.py 负责研究，gpt_researcher/skills/writer.py 负责写作。
```

### 3. 一句话下一步学习方向

```text
我已经知道主链路怎么走，下一步应该拆开看“研究阶段内部是怎么工作的”。
```

## Day 2 完成标准

如果下面这些你都做到了，今天就算完成：

- 我已经能说清楚项目的主执行链路
- 我已经知道 `tests/cli/frontend` 只是不同入口，不是不同系统
- 我已经知道 `GPTResearcher` 是总编排器
- 我已经知道研究和写报告为什么分成两步
- 我已经知道 Day 3 应该去看检索、抓取和上下文整理

## 明天学什么

Day 3 建议直接进入“研究流程内部”。

推荐阅读顺序：

1. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)
2. [gpt_researcher/actions/retriever.py](../gpt_researcher/actions/retriever.py)
3. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
4. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
5. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)

如果 Day 2 是在学“主干”，那么 Day 3 才是真正开始学“研究到底是怎么做出来的”。
