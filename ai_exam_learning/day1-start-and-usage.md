# Day 1：项目启动与第一次使用

## 今日目标

今天只做两件事：

1. 把项目成功启动起来。
2. 真正跑通一次完整的研究流程。

今天不要急着通读代码。先通过“实际使用”建立对这个项目的第一层理解。

## 这个项目在做什么

GPT Researcher 的核心流程可以先粗略理解成：

1. 输入一个研究问题。
2. 去网页或本地文档里找资料。
3. 对资料做筛选和整理。
4. 生成一份研究报告。
5. 在报告生成之后，还可以继续围绕这份报告追问。

## Day 1 学习范围

做完今天，你应该能回答下面这些问题：

1. 这个项目怎么启动？
2. `8000` 和 `3000` 这两个启动方式有什么区别？
3. UI 里最重要的几个设置项是什么？
4. 我怎么从浏览器里发起一次研究任务？
5. 报告生成后，怎么继续体验这个 agent 的能力？

## 启动前准备

你至少需要这些条件：

1. Python 3.11 或更高版本
2. 已经创建好的虚拟环境
3. 一个大模型提供方
4. 一个搜索提供方

Day 1 推荐你走下面两条路径中的一条。

### 方案 A：云端稳定方案

如果你的目标是“最快成功跑起来”，优先用这个。

`.env` 示例：

```env
OPENAI_API_KEY=your_key
TAVILY_API_KEY=your_key

FAST_LLM=openai:gpt-4o-mini
SMART_LLM=openai:gpt-4.1
STRATEGIC_LLM=openai:o4-mini
EMBEDDING=openai:text-embedding-3-small
RETRIEVER=tavily
DOC_PATH=./my-docs
```

### 方案 B：本地低成本方案

如果你想先用本地模型体验，可以用这个。

`.env` 示例：

```env
OLLAMA_BASE_URL=http://localhost:11434

FAST_LLM=ollama:llama3
SMART_LLM=ollama:llama3
STRATEGIC_LLM=ollama:llama3
EMBEDDING=ollama:nomic-embed-text
RETRIEVER=duckduckgo
DOC_PATH=./my-docs
```

如果你走 Ollama 方案，先把模型拉下来：

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

## 本次实战推荐配置

如果你当前这台机器继续沿用今天已经跑通的方案，推荐直接使用下面这套：

```env
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
OPENAI_API_KEY=你的_ARK_KEY

FAST_LLM=openai:ep-20260225100049-hpq2z
SMART_LLM=openai:ep-20260225095852-lcvpm
STRATEGIC_LLM=openai:ep-20260225095852-lcvpm

OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING=ollama:nomic-embed-text

RETRIEVER=duckduckgo
MCP_STRATEGY=disabled
LANGUAGE=Chinese
DOC_PATH=./my-docs
```

这套配置的含义是：

1. 豆包 ARK 负责 `chat/completions`
2. Ollama 负责 `embedding`
3. DuckDuckGo 负责网页检索
4. 默认输出语言为中文
5. 先关闭 MCP，避免第一天就被 `npx` 和多进程问题干扰

## 安装依赖

在项目根目录执行：

```bash
python -m pip install -r requirements.txt
```

如果你当前机器还存在 `pip SSL` 证书问题，先解决证书问题，再继续安装依赖。

如果你后面要启用 MCP，还要额外准备：

1. Node.js
2. `npx`

如果你后面要启用本地 embedding，还要额外准备：

1. Ollama
2. `nomic-embed-text`

## 项目怎么启动

### 启动方式 1：后端 + 静态前端

这是最简单、最适合 Day 1 的启动方式。

```bash
python -m uvicorn main:app --reload
```

然后打开：

```text
http://localhost:8000
```

这一种方式会同时给你：

1. FastAPI 后端
2. 一个由后端直接提供的静态前端
3. 研究过程中的实时日志输出

### 启动方式 2：后端 + Next.js 前端

如果你想体验更完整的 UI，可以用这一种。

先启动后端：

```bash
python -m uvicorn main:app --reload
```

然后打开第二个终端：

```bash
cd frontend/nextjs
npm install --legacy-peer-deps
NEXT_PUBLIC_GPTR_API_URL=http://localhost:8000 npm run dev
```

然后访问：

```text
http://localhost:3000
```

你可以先记住区别：

1. `8000`：更简单，更适合第一天上手。
2. `3000`：前端体验更完整，但需要多开一个前端进程。

## 第一次完整体验应该怎么做

Day 1 不要一上来就选最复杂的模式。

推荐第一轮配置：

1. `Report Type` 选择 `research_report`
2. `Report Source` 选择 `web`
3. `Tone` 选择 `Objective`
4. 先不要打开 MCP
5. 先不要用 `deep`
6. 先不要用 `multi_agents`

推荐第一轮问题：

```text
What are the main open source AI agent frameworks and how do they differ?
```

你也可以换成中文问题，但第一轮建议问一个你本身就大概了解的话题，方便对比结果质量。

## 第一次运行时你要重点观察什么

第一轮体验，不要只盯着最后那份报告。

你应该重点观察这几件事：

1. 页面里会先持续输出研究日志，而不是一下子直接给答案。
2. 系统会先找资料，再组织资料，最后才生成报告。
3. 这个项目的核心不是“聊天”，而是“研究工作流”。

## Day 1 实战排错记录

这一节很重要。下面这些不是泛泛而谈，而是这次实际启动过程中已经踩到并解决的问题。

### 1. `pip install` 的 SSL 证书错误

现象：

- `Could not fetch URL https://pypi.org/...`
- `SSLCertVerificationError`

本质：

1. 不是 `requirements.txt` 写错了
2. 是本机 Python 证书链有问题

处理思路：

1. 先修 Python / pip 的证书环境
2. 再安装依赖

这个问题属于环境问题，不是项目代码问题。

### 2. 豆包 ARK 可以跑对话，但默认 embedding 不可用

现象：

- `chat/completions` 返回 `200 OK`
- `embeddings` 返回 `404 Not Found`
- 报错里会出现 `text-embedding-3-small does not exist`

本质：

1. 项目默认 embedding 是 `openai:text-embedding-3-small`
2. 当你把 `OPENAI_BASE_URL` 指到 ARK 后，默认 embedding 也会一起走 ARK
3. 但 ARK 不一定提供这个 embedding 模型

处理方式：

1. 不再让 embedding 走 ARK
2. 改成 `EMBEDDING=ollama:nomic-embed-text`

这也是为什么今天最终采用了“豆包 + Ollama embedding”的组合。

### 3. Ollama 的作用不是替代豆包，而是补齐 embedding

在今天这套方案里：

1. 豆包负责生成研究计划、写报告、聊天补充
2. Ollama 只负责向量化和上下文相关性筛选

你至少要会这几个命令：

```bash
ollama --version
ollama serve
ollama pull nomic-embed-text
curl http://localhost:11434/api/tags
```

如果 `ollama serve` 提示 `address already in use`，一般不是错误，而是 Ollama 已经在后台运行。

### 4. MCP 依赖 `Node.js` 和 `npx`

现象：

- `Error getting MCP tools: [Errno 2] No such file or directory: 'npx'`

本质：

1. 你在页面里启用了 MCP
2. 但本机没有 `npx`
3. 所以 MCP Server 根本没法启动

处理方式：

1. 安装 `Node.js`
2. 确认 `node -v`
3. 确认 `npx -v`
4. 然后再启用 MCP

第一天如果你只想先把主流程跑通，建议先把 `MCP_STRATEGY=disabled`。

### 5. 聊天补搜索和研究主流程不是同一套检索器

这是一个非常容易误解的点。

研究阶段：

1. 会读取 `.env` 里的 `RETRIEVER`
2. 你今天配置的是 `duckduckgo`

聊天阶段：

1. 原始实现里并不读取 `RETRIEVER`
2. 它原来单独依赖 `TAVILY_API_KEY`

所以你会看到：

1. 研究能搜索
2. 聊天追问时却提示 `TAVILY_API_KEY not set`

今天已经把这里改成了更合理的策略：

1. 有 `TAVILY_API_KEY` 就用 Tavily
2. 没有就自动 fallback 到 DuckDuckGo

这属于一个很典型的“产品逻辑一致性”修复。

### 6. 豆包流式写报告时，可能出现 `200 OK` 但正文为空

现象：

1. `POST ... /chat/completions` 显示 `200 OK`
2. 但日志里提示 `LLM returned empty response`
3. 原始实现还可能错误地继续打印 `Report written`

本质：

1. 研究阶段已经成功
2. 问题出在“最终写报告”这一步
3. 某些 OpenAI 兼容接口在流式输出上不完全稳定

今天已经做了两项修复：

1. 流式写报告失败时，自动回退到非流式
2. 空报告时不再假装成功，而是明确按失败处理

### 7. PDF 导出失败，不代表研究失败

现象：

- `WeasyPrint could not import some external libraries`
- `cannot load library 'libgobject-2.0-0'`

本质：

1. 这是本机缺少 PDF 导出的原生依赖
2. 不是研究流程失败
3. `docx` 和 `md` 仍然可以正常生成

今天已经把这部分优化成：

1. 检测到本机缺少 PDF 依赖时
2. 直接跳过 PDF 导出
3. 不再让主流程被一段长错误日志污染

所以你现在看到：

```text
Skipping PDF export: missing native PDF dependencies: cairo, glib, pango, pango+cairo
```

这不是新错误，而是更干净的降级行为。

### 8. 报告默认是英文，因为默认配置就是英文

本质：

1. 项目默认 `LANGUAGE=english`
2. prompt 会把这个字段直接写进“报告输出语言”要求里

处理方式：

在 `.env` 中加入：

```env
LANGUAGE=Chinese
```

然后重启后端，重新生成一份新报告。

### 9. `localhost:8000` 静态前端默认是英文

第一天体验时，一个实际感受问题是：

1. 后端能跑
2. 但静态前端默认大部分文案是英文

今天已经把 `8000` 这套静态前端主要文案改成了中文，适合你继续用这套页面做 Day 1 体验。

## Day 1 中已经完成的代码修复

如果你后面开始读源码，这些改动值得记一下，因为它们都和“第一天怎么把项目真正跑起来”直接相关。

1. `backend/server/websocket_manager.py`
   修复了缺少 `os` 导入导致的启动研究任务时报错。
2. `backend/server/websocket_manager.py`
   把 `report_type` 的不稳定导入改成了明确包路径，消除 IDE 未解析引用。
3. `gpt_researcher/actions/report_generation.py`
   给最终成文增加了“流式失败 -> 非流式回退”。
4. `gpt_researcher/skills/writer.py`
   避免空报告时仍然打印 `Report written`。
5. `backend/utils.py`
   缺少 PDF 原生依赖时跳过 PDF 导出，不影响 `docx/md`。
6. `backend/chat/chat.py`
   聊天补搜索改为“优先 Tavily，缺失时自动回退 DuckDuckGo”。
7. `frontend/index.html` 与 `frontend/scripts.js`
   静态前端主文案汉化，便于中文使用。

## Day 1 建议体验顺序

按这个顺序体验，最容易建立感觉。

### 1. 先跑一次最基础的 Web Research

目标：

1. 确认项目能启动
2. 确认模型配置没问题
3. 确认搜索流程能正常工作

### 2. 再切换 `Report Type`

至少对比这两种：

1. `research_report`
2. `detailed_report`

重点关注：

1. 输出长度变化
2. 结构变化
3. 完成时间变化

### 3. 再试 `Report Source`

至少感受这三种：

1. `web`
2. `local`
3. `hybrid`

如果要试 `local` 或 `hybrid`，就把文件放到：

```text
./my-docs
```

适合放进去的文件类型：

1. Markdown 笔记
2. PDF 文档
3. 一些项目说明文档

### 4. 再试 Domain Filter

例如限制来源为：

1. `github.com`
2. `arxiv.org`
3. `docs.langchain.com`

这一轮的目标是理解：

这个项目不是单纯“让模型随便回答”，而是可以在约束信息源的前提下做研究。

### 5. 最后试报告后的追问

报告生成之后，再继续问：

1. “把这份报告压缩成 5 条结论”
2. “如果我是小团队，应该优先选哪个框架”
3. “这份报告里哪些判断可能不够稳”

这一轮的目标是理解：

这个项目支持“基于已生成报告继续聊天”，而不是每次都从零开始。

## 可选：用 CLI 体验一次

如果你想暂时绕开前端，也可以直接从命令行跑一次：

```bash
python cli.py "What are the main open source AI agent frameworks?" --report_type research_report --tone objective --report_source web
```

CLI 在后面学代码主链路时会很有帮助，因为它比前端路径更直接。

## Day 1 的最小心智模型

今天先记住这一句就够了：

```text
问题 -> 搜索/文档 -> 上下文整理 -> 生成报告 -> 基于报告继续追问
```

这就是你今天最应该建立起来的第一层理解。

## Day 1 完成标准

如果下面这些你都做到了，今天就算完成：

- 我已经准备好 `.env`
- 我已经安装完依赖
- 我已经成功启动后端
- 我已经打开 `http://localhost:8000` 或 `http://localhost:3000`
- 我已经成功跑过一次 `research_report`
- 我已经改过至少一个 UI 设置
- 我已经在报告生成后继续追问过至少一次
- 我已经知道哪些错误属于“环境问题”，哪些属于“项目代码问题”
- 我已经知道当前这台机器上 `docx/md` 是稳定可用的，`pdf` 被主动跳过

## 今天结束后你应该自己回答的问题

建议你真的自己写一下答案：

1. 我今天走的是哪条启动路径？
2. 我今天用的是哪个模型提供方？
3. 我今天用的是哪个搜索提供方？
4. `research_report` 和 `detailed_report` 的实际区别是什么？
5. 这个项目最像“聊天机器人”，还是更像“研究流水线”？

## 明天学什么

Day 2 再开始看代码主链路，不要今天就把自己带进源码细节里。

推荐 Day 2 阅读顺序：

1. `tests/report-types.py`
2. `cli.py`
3. `gpt_researcher/agent.py`
4. `gpt_researcher/skills/researcher.py`
5. `gpt_researcher/skills/writer.py`
