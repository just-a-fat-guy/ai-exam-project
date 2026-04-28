# Day 3：研究流程与 LLM 决策点分布图

## 今日目标

Day 2 你已经看完了主执行链路。  
Day 3 的重点不再是“主干怎么串起来”，而是进一步回答两个更本质的问题：

1. 研究阶段内部到底是怎么工作的？
2. 这个项目里，哪些地方是代码在执行，哪些地方是大模型在做决策？

今天学完之后，你应该能明确区分下面两种东西：

```text
程序流程控制
vs
LLM 语义决策
```

这一步非常关键。  
如果你分不清这两个层次，就很容易把整个项目误认为“全靠 prompt 硬写出来”。

## Day 3 学习范围

今天主要看下面这些文件：

1. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)
2. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)
3. [gpt_researcher/actions/agent_creator.py](../gpt_researcher/actions/agent_creator.py)
4. [gpt_researcher/skills/curator.py](../gpt_researcher/skills/curator.py)
5. [gpt_researcher/mcp/tool_selector.py](../gpt_researcher/mcp/tool_selector.py)
6. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
7. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
8. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)
9. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)
10. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)
11. [gpt_researcher/utils/llm.py](../gpt_researcher/utils/llm.py)

## 今天先建立一个总图

先把整个流程记成下面这张图：

```text
用户问题
-> 选择研究角色
-> 初始搜索
-> 规划子查询
-> 多轮检索 / 抓取 / 过滤
-> 整理成 context
-> 写报告结构
-> 生成正文 / 引言 / 结论
-> 输出 md / docx / pdf / 前端展示
-> 可继续围绕报告聊天追问
```

其中：

- `检索 / 抓取 / 压缩` 主要是程序执行
- `角色选择 / 子查询规划 / 工具选择 / 来源筛选 / 报告写作` 主要是 LLM 决策

## Day 3 推荐阅读顺序

建议按下面这个顺序读，不要打乱。

### 第 1 站：研究阶段总控

先读：

1. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)

重点看：

1. `plan_research()`
2. `conduct_research()`
3. `_get_context_by_web_search()`
4. `_process_sub_query()`

你要回答的问题：

1. 主问题什么时候会被拆成子查询？
2. 子查询是并发执行还是串行执行？
3. 网页抓取、MCP、向量压缩分别接在哪一步？
4. 最终 `context` 是在哪里合并出来的？

### 第 2 站：子查询规划

接着读：

1. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)

重点看：

1. `generate_sub_queries()`
2. `plan_research_outline()`
3. `get_search_results()`

这一层的关键理解是：

```text
程序先搜一轮
-> 把搜索结果交给模型
-> 模型再决定下一步该研究哪些子问题
```

这就是这个项目“不是直接搜一下就写报告”的核心原因。

### 第 3 站：研究角色与研究身份

然后读：

1. [gpt_researcher/actions/agent_creator.py](../gpt_researcher/actions/agent_creator.py)

重点看：

1. `choose_agent()`
2. `handle_json_error()`

这一层要理解：

1. 为什么同一个问题会先选一个“研究角色”
2. 这个角色最后是怎么变成 `agent_role_prompt` 的
3. 为什么后面研究规划和报告写作都会复用这个角色 prompt

### 第 4 站：来源筛选和 MCP 工具选择

接着读：

1. [gpt_researcher/skills/curator.py](../gpt_researcher/skills/curator.py)
2. [gpt_researcher/mcp/tool_selector.py](../gpt_researcher/mcp/tool_selector.py)

你要理解：

1. 来源筛选不是纯规则，而是 LLM 决定“哪些来源更值得保留”
2. MCP 也不是把所有工具全跑一遍，而是先让模型挑工具

这两层都属于比较典型的 agent 决策。

### 第 5 站：真正的执行层

最后再回头读：

1. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
2. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
3. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)

这时候你会更容易看出：

- 这些文件很重要
- 但它们大多不是“大模型在做主观决策”
- 它们更像是在执行前面 LLM 已经规划好的研究路径

## 研究流程真正是怎么跑的

下面按时间顺序梳理一遍。

### 1. 先选研究角色

位置：

1. [gpt_researcher/actions/agent_creator.py](../gpt_researcher/actions/agent_creator.py)
2. [gpt_researcher/agent.py](../gpt_researcher/agent.py)
3. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

这里的本质是：

```text
query
-> auto_agent_instructions prompt
-> LLM 返回 server + agent_role_prompt
```

这一步不是生成报告，而是在决定：

1. 这次研究应该以什么身份来做
2. 后面所有 prompt 应该带着什么角色语气

### 2. 先做一次初始搜索

位置：

1. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)
2. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)

这一步程序会做的事情是：

1. 调用 retriever
2. 拿到一批原始搜索结果

这一步本身不是大模型决策。  
它只是给后面“子查询规划”提供原料。

### 3. 让模型规划子查询

位置：

1. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

这一步是 Day 3 最核心的研究决策点之一。

逻辑是：

```text
原问题 + 初始搜索结果
-> generate_search_queries_prompt()
-> strategic/smart LLM
-> 返回 sub_queries
```

也就是说：

- 搜索器没有决定“接下来查什么”
- 是大模型在决定“接下来该拆成哪些研究子问题”

### 4. 按子查询去做检索与抓取

位置：

1. [gpt_researcher/skills/researcher.py](../gpt_researcher/skills/researcher.py)
2. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)

这一层更偏执行：

1. 根据子查询去搜索
2. 选出 URL
3. 抓正文
4. 抓图片

这里的“做不做、怎么抓、怎么并发”主要是程序逻辑。

### 5. 用 embedding / 相似度压缩上下文

位置：

1. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
2. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)

这一步非常容易误解。

这里虽然也在“筛选信息”，但它大多不是 LLM 决策，而是：

1. 文本切块
2. embedding
3. 相似度检索
4. `EmbeddingsFilter`

所以更准确地说：

```text
这是语义检索 / 向量筛选
不是大模型主观规划
```

### 6. 来源筛选

位置：

1. [gpt_researcher/skills/curator.py](../gpt_researcher/skills/curator.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

这一步又回到了 LLM 决策：

1. 哪些来源更相关
2. 哪些来源更可信
3. 哪些来源更有统计价值

这一步是“对研究结果再做一次语义级判断”。

### 7. 把 context 交给写作阶段

位置：

1. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)
2. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)

到这一步，研究阶段就结束了。  
写作阶段会基于 `context` 再让模型决定：

1. 报告怎么组织
2. 哪些信息应该进正文
3. 结论怎么落

## LLM 决策点分布图

下面这张图是 Day 3 最重要的内容。

### 总图

```text
研究前
  - 选择研究角色
  - 设定角色 prompt

研究中
  - 规划子查询
  - 选择 MCP 工具
  - 筛选来源
  - 决定某些结构化子任务输出

写作中
  - 生成子主题
  - 生成章节标题
  - 生成正文 / 引言 / 结论
  - 综合证据并形成结论

输出后
  - 围绕已有报告继续聊天
  - 必要时做 quick search / tool calling
  - 文件导出本身不是 LLM 决策
```

## 按四个阶段展开

### 一、研究前

这一阶段最典型的 LLM 决策只有一个，但非常关键：

#### 1. 选择研究角色

位置：

1. [gpt_researcher/actions/agent_creator.py](../gpt_researcher/actions/agent_creator.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

输入：

1. 用户问题
2. 自动选 agent 的 prompt

输出：

1. `server`
2. `agent_role_prompt`

这一步的意义：

1. 决定后续提示词里的身份设定
2. 决定研究风格和报告写作风格

这一步不是纯装饰，它会影响后面整条链路。

### 二、研究中

这一阶段的 LLM 决策最多。

#### 1. 子查询规划

位置：

1. [gpt_researcher/actions/query_processing.py](../gpt_researcher/actions/query_processing.py)

输入：

1. 原问题
2. 初始搜索结果
3. 报告类型

输出：

1. `sub_queries`

这一步是研究阶段最重要的“规划型决策”。

#### 2. MCP 工具选择

位置：

1. [gpt_researcher/mcp/tool_selector.py](../gpt_researcher/mcp/tool_selector.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

输入：

1. 当前 query
2. 可用 MCP tools 列表

输出：

1. 最相关的一组工具

这一步属于标准 agent 模式：

```text
先看工具列表
-> 再决定调用哪些工具
```

#### 3. 来源筛选

位置：

1. [gpt_researcher/skills/curator.py](../gpt_researcher/skills/curator.py)

输入：

1. 抓取后的来源数据
2. 来源筛选 prompt

输出：

1. 排序后的来源列表

#### 4. 不属于 LLM 决策的部分

下面这些在研究中很重要，但不是“大模型主观判断”：

1. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
2. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
3. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)

它们主要负责：

1. 抓网页
2. 抽正文
3. embedding
4. 相似度筛选
5. 压缩 context

所以你要明确：

```text
context compression != LLM 决策
```

它更接近“语义检索层”。

### 三、写作中

这一阶段又回到模型主导。

#### 1. 生成子主题

位置：

1. [gpt_researcher/utils/llm.py](../gpt_researcher/utils/llm.py)
2. [gpt_researcher/skills/writer.py](../gpt_researcher/skills/writer.py)
3. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

输入：

1. 主任务
2. 研究 context

输出：

1. 结构化子主题列表

#### 2. 生成草稿章节标题

位置：

1. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

输入：

1. 子主题
2. 上下文

输出：

1. 一组章节标题

#### 3. 生成正文

位置：

1. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)
2. [gpt_researcher/prompts.py](../gpt_researcher/prompts.py)

输入：

1. query
2. context
3. report_type
4. tone
5. report_source
6. role prompt

输出：

1. 报告正文

这是最明显的 LLM 决策层，但它不是唯一的一层。

#### 4. 生成引言与结论

位置：

1. [gpt_researcher/actions/report_generation.py](../gpt_researcher/actions/report_generation.py)

输入：

1. query
2. 研究 summary 或 report_content

输出：

1. introduction
2. conclusion

### 四、输出后

这一阶段要分清两件事。

#### 1. 文件导出不是 LLM 决策

位置：

1. [backend/utils.py](../backend/utils.py)

`md/docx/pdf` 导出属于程序执行，不是模型判断。

#### 2. 围绕报告继续聊天时，LLM 决策会再次出现

位置：

1. [backend/chat/chat.py](../backend/chat/chat.py)
2. [gpt_researcher/utils/tools.py](../gpt_researcher/utils/tools.py)
3. [gpt_researcher/agent.py](../gpt_researcher/agent.py)

这里模型可能会做的事情包括：

1. 判断是否需要联网补搜索
2. 决定是否调用工具
3. 基于已有报告内容继续回答

所以“输出后”并不是系统结束了，  
而是进入了“基于已生成报告的二次问答阶段”。

## 这一天最重要的结论

你今天一定要记住下面这句话：

```text
GPT Researcher 不是“LLM 从头到尾自由发挥”
也不是“纯规则系统”
而是“程序流程 + LLM 决策”混合驱动的研究系统
```

再进一步说：

- 研究路线由 LLM 规划
- 资料抓取由程序执行
- 上下文压缩由 embedding 相似度完成
- 报告组织与结论由 LLM 生成

## 今天读源码时建议你重点问自己的问题

1. 这里是在“执行”还是在“决策”？
2. 这里的输入是什么？是原始网页、搜索结果，还是已经整理过的 context？
3. 这里的输出是结构化中间结果，还是最终报告文本？
4. 如果把这一处的大模型拿掉，这个环节还能不能成立？

## Day 3 结束后你应该能回答的问题

1. 为什么这个项目不是简单的“搜一下然后让模型写文章”？
2. 子查询到底是谁决定的？
3. MCP 工具到底是谁决定用哪个的？
4. context compression 为什么不等于 LLM 决策？
5. 报告正文、引言、结论分别是谁生成的？
6. 输出之后的聊天，为什么仍然可以继续触发模型决策？

## Day 4 预告

如果继续往下学，Day 4 建议专门精读：

1. [gpt_researcher/skills/browser.py](../gpt_researcher/skills/browser.py)
2. [gpt_researcher/skills/context_manager.py](../gpt_researcher/skills/context_manager.py)
3. [gpt_researcher/context/compression.py](../gpt_researcher/context/compression.py)
4. [gpt_researcher/memory/embeddings.py](../gpt_researcher/memory/embeddings.py)

主题就是：

```text
抓取、向量化、上下文压缩到底是怎么工作的
```

## AI 组卷改造：当前目录改名结果

为了开始把项目往“AI 组卷”方向迁移，我先做了一轮**安全改名**。

注意，这一轮不是“彻底改包名”，而是：

1. 先把主要目录改成 AI 组卷语义
2. 同时保留旧目录名的兼容入口
3. 避免一开始就把 imports、启动脚本、前后端路径全部改坏

当前映射关系如下：

1. [ai_exam_engine](../ai_exam_engine) 是原来的核心引擎目录，旧入口 [gpt_researcher](../gpt_researcher) 仍然保留为兼容链接
2. [ai_exam_backend](../ai_exam_backend) 是原来的后端目录，旧入口 [backend](../backend) 仍然保留为兼容链接
3. [ai_exam_frontend](../ai_exam_frontend) 是原来的前端目录，旧入口 [frontend](../frontend) 仍然保留为兼容链接
4. [ai_exam_learning](../ai_exam_learning) 是原来的学习文档目录，旧入口 [learning](../learning) 仍然保留为兼容链接

这一步的目的很明确：

```text
先把项目的“目录语义”改成 AI 组卷方向
但暂时不动 import 路径和运行链路
```

这样做的好处是：

1. 你可以先开始领域迁移，不会因为一次性全改包名而把项目跑坏
2. 后续真正做模块替换时，可以逐层去掉旧名字兼容层
3. 改造风险是可控的

## AI 组卷改造：为什么现在不直接全量改包名

你如果现在就直接把下面这些都彻底改掉：

1. `gpt_researcher.*` 的所有 import
2. `backend.*` 的所有模块引用
3. 前端 API 路径、后端启动入口、测试路径
4. `setup.py` / `pyproject.toml` 里的包声明

那么这一步会从“业务改造”瞬间变成“基础设施大迁移”。

这不适合当前阶段。  
因为你现在的目标不是先把工程名字改漂亮，而是：

```text
先把 GPT Researcher 改造成可用的 AI 组卷底座
```

所以当前策略是正确的：

1. 先改目录语义
2. 再改业务模型
3. 最后再清理兼容层和旧命名

## AI 组卷改造：逐步实施总路线

从 GPT Researcher 到 AI 组卷系统，我建议按下面 8 个阶段推进。

### 阶段 0：目录语义改名

目标：

1. 让项目目录从命名上开始脱离“Researcher”心智
2. 但保持项目依然可以运行

本阶段已完成的事情：

1. `backend -> ai_exam_backend`
2. `frontend -> ai_exam_frontend`
3. `gpt_researcher -> ai_exam_engine`
4. `learning -> ai_exam_learning`

本阶段暂不做的事情：

1. 不全量替换 Python import
2. 不全量修改包名
3. 不改 API 路由命名

### 阶段 1：先定义“AI 组卷”的领域模型

这是最重要的一步，优先级高于改 prompt。

你要先把“研究报告”模型替换成“试卷”模型。

建议新增或明确这些核心对象：

1. `ExamPaper`
2. `PaperSection`
3. `Question`
4. `Option`
5. `Answer`
6. `Explanation`
7. `KnowledgePoint`
8. `DifficultyLevel`
9. `ReviewTask`
10. `ReviewComment`

建议先落地的位置：

1. [ai_exam_backend](../ai_exam_backend)
2. [ai_exam_engine](../ai_exam_engine)

更具体地说，第一批最好新建：

1. `ai_exam_backend/schemas/`
2. `ai_exam_backend/services/`
3. `ai_exam_engine/exam/`

这一阶段的核心目标不是“先生成试卷”，而是先回答：

```text
系统里的“试卷”到底长什么样
```

### 阶段 2：把“研究任务输入”改成“组卷约束输入”

GPT Researcher 当前的主输入是：

1. query
2. report_type
3. tone
4. report_source

AI 组卷需要的主输入应该改成：

1. 学科
2. 学段 / 年级
3. 试卷类型
4. 题型分布
5. 总题量
6. 总分
7. 难度分布
8. 知识点范围
9. 是否允许 AI 新生成题
10. 是否只允许从题库抽题

要改的核心位置：

1. [ai_exam_frontend](../ai_exam_frontend) 的表单组件
2. [ai_exam_backend/server](../ai_exam_backend/server) 的请求模型
3. [ai_exam_engine/agent.py](../ai_exam_engine/agent.py) 的初始化参数

这一步完成后，系统就不再以“研究问题”为主输入，而是以“组卷约束”为主输入。

### 阶段 3：替换数据来源，从“网页研究”转向“题库 / 教材 / 考纲”

这是业务本质变化最大的一步。

当前项目偏向：

1. web search
2. URL scraping
3. context compression
4. report synthesis

AI 组卷系统应优先变成：

1. 题库检索
2. 教材知识点检索
3. 课程标准 / 考纲检索
4. 历史试卷检索
5. 教师上传资料检索

这里建议保留和替换的关系如下：

保留：

1. 向量检索能力
2. 文档加载能力
3. 上下文压缩能力

替换：

1. 通用网页 retriever 的优先级
2. 面向新闻/网页的报告型 prompt

建议新增目录：

1. `ai_exam_engine/question_bank/`
2. `ai_exam_engine/syllabus/`
3. `ai_exam_engine/review/`

### 阶段 4：把“研究规划”改成“组卷规划”

当前研究规划是：

```text
query -> sub_queries -> 搜索 -> context -> report
```

AI 组卷规划应改成：

```text
组卷要求
-> 生成试卷蓝图
-> 为每个题型 / 知识点分配题目
-> 抽题或生成题
-> 组装试卷草稿
```

当前可复用的代码：

1. [ai_exam_engine/actions/query_processing.py](../ai_exam_engine/actions/query_processing.py)
2. [ai_exam_engine/actions/agent_creator.py](../ai_exam_engine/actions/agent_creator.py)
3. [ai_exam_engine/prompts.py](../ai_exam_engine/prompts.py)

但要替换它们的语义：

1. `generate_sub_queries()` 不再输出“研究子查询”
2. 改成输出“组卷蓝图子任务”
3. `choose_agent()` 不再只分 Finance / Travel / Research
4. 改成 Teacher / Exam Designer / Reviewer 这类教育角色

### 阶段 5：把“报告生成”改成“试卷生成 + 解析生成”

当前生成层的核心是：

1. [ai_exam_engine/skills/writer.py](../ai_exam_engine/skills/writer.py)
2. [ai_exam_engine/actions/report_generation.py](../ai_exam_engine/actions/report_generation.py)
3. [ai_exam_engine/prompts.py](../ai_exam_engine/prompts.py)

这一层后面要逐步演化成：

1. `paper_generation.py`
2. `question_generation.py`
3. `answer_generation.py`
4. `explanation_generation.py`

建议第一步不是直接删掉原来的 `writer.py`，而是：

1. 保留现有写作链路
2. 新增 `exam_writer.py` 或 `paper_writer.py`
3. 先让新的组卷流程和旧的报告流程并存

这样更稳。

建议第一版输出结构为 JSON，而不是直接 Word：

```json
{
  "paper_title": "",
  "subject": "",
  "grade": "",
  "sections": [
    {
      "section_name": "",
      "question_type": "",
      "questions": []
    }
  ]
}
```

原因很简单：

1. JSON 更适合程序校验
2. 更适合人工审核
3. 更适合后续导出成 Word / PDF / 在线编辑界面

### 阶段 6：新增“人工审核”闭环

这是 GPT Researcher 原始项目里没有的关键能力。

AI 组卷系统必须新增：

1. 试卷草稿状态
2. 审核状态
3. 审核意见
4. 驳回重提
5. 版本管理
6. 最终定稿

建议新增模块：

1. `ai_exam_backend/review/`
2. `ai_exam_backend/workflows/`
3. `ai_exam_engine/review/`

前端需要新增页面：

1. 试卷草稿页
2. 题目逐题审核页
3. 审核意见面板
4. 修订历史页

这一阶段完成后，系统才真正从“AI 自动生成内容”变成“AI 辅助 + 人工把关”的业务系统。

### 阶段 7：补规则校验层

AI 组卷不是只要模型写得通顺就行。  
必须增加规则层校验。

建议最少加这些校验：

1. 题目是否重复
2. 答案是否缺失
3. 选项数量是否正确
4. 题型和分值是否匹配
5. 难度分布是否符合要求
6. 知识点覆盖是否符合要求
7. 解析是否和答案一致

建议新增：

1. `ai_exam_engine/validators/`
2. `ai_exam_engine/rules/`

这一步做完后，AI 组卷结果才具备基本工程质量。

### 阶段 8：最后再清理兼容层和旧命名

这一阶段才去做“真正彻底的改名”。

包括：

1. 把代码里的 `gpt_researcher.*` import 全量迁移到 `ai_exam_engine.*`
2. 把 `backend.*` 引用全量迁移到 `ai_exam_backend.*`
3. 更新 `setup.py` / `pyproject.toml`
4. 更新启动脚本
5. 删除兼容链接

注意：

```text
这一步必须放到最后
```

因为它不会直接提升业务价值，但会显著增加改造风险。

## 建议你的最小可行改造顺序

如果你不想一下子改太大，我建议按下面这个顺序落地。

### 第一步：先让系统能输入“组卷要求”

目标：

1. 前端可以录入学科、年级、题型、题量、难度
2. 后端能接收到结构化组卷请求

暂时不要做：

1. 人工审核
2. 复杂导出
3. 教学资源权限体系

### 第二步：生成“试卷蓝图”，先不直接生成题

输出例如：

1. 第一部分单选题 10 题
2. 第二部分填空题 5 题
3. 第三部分主观题 3 题
4. 每部分覆盖哪些知识点

这是最低风险的一步，因为它先验证“规划能力”，不急着验证“出题质量”。

### 第三步：先接题库抽题，再接 LLM 出题

顺序必须是：

1. 先题库抽题
2. 再 LLM 补题

不要反过来。  
因为纯 LLM 出题的稳定性和可控性太差。

### 第四步：生成答案和解析

这一层需要和题目生成拆开做，不要一口气全混在一个 prompt 里。

### 第五步：补人工审核页面

这一步做完，系统才进入“真实可用”的阶段。

## 哪些旧模块最值得保留

真正有价值的，不是“Researcher”这个名字，而是它的底层骨架。

建议保留：

1. [ai_exam_engine/utils/llm.py](../ai_exam_engine/utils/llm.py)
2. [ai_exam_engine/prompts.py](../ai_exam_engine/prompts.py)
3. [ai_exam_engine/skills/context_manager.py](../ai_exam_engine/skills/context_manager.py)
4. [ai_exam_engine/context/compression.py](../ai_exam_engine/context/compression.py)
5. [ai_exam_backend/server](../ai_exam_backend/server)
6. [ai_exam_frontend/nextjs](../ai_exam_frontend/nextjs)

这些是“技术骨架”。

## 哪些旧模块后续会被明显替换

1. 通用网页研究主流程
2. 报告类型体系 `report_type`
3. 研究报告 prompt
4. 面向 web search 的默认 UI 交互

## 当前阶段你最应该记住的结论

改这个项目，不是“把 Research 把词替换成 Exam”就够了。

真正正确的路径是：

```text
先改目录语义
-> 再改领域模型
-> 再改输入输出
-> 再改业务工作流
-> 最后清理旧命名和兼容层
```
