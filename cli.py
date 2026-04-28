"""GPT Researcher 的命令行入口。

学习这个文件的目的，不是记住所有命令行参数，而是看清楚：

1. 命令行参数如何映射成 `GPTResearcher(...)` 的构造参数
2. CLI 与测试入口、本地网页入口，本质上是不是同一条主链路
3. 报告生成完成后，结果是如何落盘到 `outputs/` 的

最核心的事实只有一个：
CLI 不是另一套系统，它只是把“用户输入”换成了命令行参数。
后面真正执行研究与写报告的，依然是同一个核心类。
"""
import asyncio
import argparse
from argparse import RawTextHelpFormatter
from uuid import uuid4
import os

from dotenv import load_dotenv

from gpt_researcher import GPTResearcher
from gpt_researcher.utils.enum import ReportType, ReportSource, Tone
from backend.report_type import DetailedReport
from backend.utils import write_md_to_pdf, write_md_to_word

# =============================================================================
# CLI 参数定义区
# =============================================================================
#
# 这里要先澄清一个概念：
# 在 Web 页面里，“用户输入”通常来自表单输入框；
# 在 CLI 模式里，“用户输入”不是来自页面，而是来自用户在终端里敲的命令。
#
# 例如用户执行：
#   python cli.py "中国武汉房价" --report_type research_report --tone objective
#
# 这行命令会经历下面这条链路：
# 1. shell 先把整行命令拆成一组参数（argv）
# 2. argparse 根据下面的 add_argument 定义去解析这些参数
# 3. 解析结果被放进 `args` 这个命名空间对象里
# 4. `main(args)` 再把它们映射成 `GPTResearcher(...)` 的构造参数
#
# 所以 CLI 并没有“自己发明一套输入方式”，只是把“页面表单输入”
# 换成了“终端命令参数输入”。

cli = argparse.ArgumentParser(
    description="Generate a research report.",
    # 允许 help 文本里保留换行，方便把多行说明展示得更清楚。
    formatter_class=RawTextHelpFormatter)

# =====================================
# Arg: Query
# =====================================

cli.add_argument(
    # 位置参数，调用 CLI 时必须第一个提供。
    "query",
    type=str,
    help="The query to conduct research on.")

# =====================================
# Arg: Report Type
# =====================================

choices = [report_type.value for report_type in ReportType]

report_type_descriptions = {
    ReportType.ResearchReport.value: "Summary - Short and fast (~2 min)",
    ReportType.DetailedReport.value: "Detailed - In depth and longer (~5 min)",
    ReportType.ResourceReport.value: "",
    ReportType.OutlineReport.value: "",
    ReportType.CustomReport.value: "",
    ReportType.SubtopicReport.value: "",
    ReportType.DeepResearch.value: "Deep Research"
}

cli.add_argument(
    "--report_type",
    type=str,
    help="The type of report to generate. Options:\n" + "\n".join(
        f"  {choice}: {report_type_descriptions[choice]}" for choice in choices
    ),
    # 这里把枚举转换成字符串列表，供 argparse 做合法值校验。
    choices=choices,
    required=True)

# =====================================
# Arg: Tone
# =====================================

cli.add_argument(
    "--tone",
    type=str,
    help="The tone of the report (optional).",
    choices=["objective", "formal", "analytical", "persuasive", "informative",
            "explanatory", "descriptive", "critical", "comparative", "speculative",
            "reflective", "narrative", "humorous", "optimistic", "pessimistic"],
    default="objective"
)

# =====================================
# Arg: Encoding
# =====================================

cli.add_argument(
    "--encoding",
    type=str,
    help="The encoding to use for the output file (default: utf-8).",
    default="utf-8"
)

# =====================================
# Arg: Query Domains
# =====================================

cli.add_argument(
    "--query_domains",
    type=str,
    help="A comma-separated list of domains to search for the query.",
    default=""
)

# =====================================
# Arg: Report Source
# =====================================

cli.add_argument(
    "--report_source",
    type=str,
    help="The source of information for the report.",
    choices=["web", "local", "hybrid", "azure", "langchain_documents",
             "langchain_vectorstore", "static"],
    default="web"
)

# =====================================
# Arg: Output Format Flags
# =====================================

cli.add_argument(
    "--no-pdf",
    action="store_true",
    help="Skip PDF generation (generate markdown and DOCX only)."
)

cli.add_argument(
    "--no-docx",
    action="store_true",
    help="Skip DOCX generation (generate markdown and PDF only)."
)

# =============================================================================
# Main
# =============================================================================

async def main(args):
    """CLI 主执行函数。

    参数说明：
        args:
            由 `argparse` 解析得到的命名空间对象。
            这里面已经包含了命令行传入的 query、report_type、tone、
            query_domains、report_source、no_pdf、no_docx 等配置。

    主链路说明：
        1. 先把 CLI 参数转换成内部对象可接受的格式
        2. 创建 `DetailedReport` 或 `GPTResearcher`
        3. 先执行 `conduct_research()`
        4. 再执行 `write_report()`
        5. 最后把结果写入 markdown / pdf / docx

    输入来源说明：
        这里的 `args` 不是代码里手工构造出来的，
        而是 `argparse.parse_args()` 从命令行参数里解析出来的。
        也就是说，CLI 模式下所谓“用户输入”，本质就是终端命令里的参数。
    """
    # 命令行里传入的是 "a.com,b.com" 这种字符串；
    # 业务代码真正需要的是 list[str]，所以这里先做一次拆分。
    query_domains = args.query_domains.split(",") if args.query_domains else []

    if args.report_type == 'detailed_report':
        # `detailed_report` 不是直接走 GPTResearcher 的默认两步调用，
        # 而是走后端封装过的 DetailedReport 对象。
        # 这说明“报告类型”不只是 prompt 差异，也可能决定执行编排类。
        detailed_report = DetailedReport(
            query=args.query,
            query_domains=query_domains,
            report_type="research_report",
            report_source="web_search",
        )

        report = await detailed_report.run()
    else:
        # CLI 读到的是字符串，例如 "objective"；
        # 内部核心类更偏向使用枚举对象 Tone.Objective。
        # 所以这里做一层映射，把“简单字符串”转换成“强类型枚举”。
        tone_map = {
            "objective": Tone.Objective,
            "formal": Tone.Formal,
            "analytical": Tone.Analytical,
            "persuasive": Tone.Persuasive,
            "informative": Tone.Informative,
            "explanatory": Tone.Explanatory,
            "descriptive": Tone.Descriptive,
            "critical": Tone.Critical,
            "comparative": Tone.Comparative,
            "speculative": Tone.Speculative,
            "reflective": Tone.Reflective,
            "narrative": Tone.Narrative,
            "humorous": Tone.Humorous,
            "optimistic": Tone.Optimistic,
            "pessimistic": Tone.Pessimistic
        }

        # 这里就是 CLI 最值得学习的一段：
        # 你可以直接看到命令行参数是如何映射到 GPTResearcher 构造参数的。
        #
        # 参数含义：
        # - query: 用户要研究的问题
        # - query_domains: 域名限制，控制搜索来源
        # - report_type: 选择报告类型
        # - report_source: 选择数据来源，web/local/hybrid 等
        # - tone: 报告写作语气
        # - encoding: 输出编码；这里主要影响本地写文件流程
        researcher = GPTResearcher(
            query=args.query,
            query_domains=query_domains,
            report_type=args.report_type,
            report_source=args.report_source,
            tone=tone_map[args.tone],
            encoding=args.encoding
        )

        # 第一步：执行研究。
        # 这一步会生成后续写报告所需的 context。
        await researcher.conduct_research()

        # 第二步：执行写作。
        # 这一步会基于 research 阶段得到的 context 生成最终报告文本。
        report = await researcher.write_report()

    # 先落盘 markdown，这是最基础、最稳的输出格式。
    task_id = str(uuid4())
    artifact_filepath = f"outputs/{task_id}.md"
    os.makedirs("outputs", exist_ok=True)
    with open(artifact_filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to '{artifact_filepath}'")

    # 如果没有显式关闭 PDF 导出，就继续尝试生成 PDF。
    # 这里用 try/except 包住，是因为 PDF 依赖系统库，比较容易受本机环境影响。
    if not args.no_pdf:
        try:
            pdf_path = await write_md_to_pdf(report, task_id)
            if pdf_path:
                print(f"PDF written to '{pdf_path}'")
        except Exception as e:
            print(f"Warning: PDF generation failed: {e}")

    # DOCX 导出与 PDF 导出分开处理。
    # 这样即使 PDF 失败，也不会影响 DOCX 产物生成。
    if not args.no_docx:
        try:
            docx_path = await write_md_to_word(report, task_id)
            if docx_path:
                print(f"DOCX written to '{docx_path}'")
        except Exception as e:
            print(f"Warning: DOCX generation failed: {e}")

if __name__ == "__main__":
    # 先加载 `.env`，让 API Key、模型、检索器等配置能被 CLI 感知到。
    load_dotenv()

    # `parse_args()` 会读取当前进程启动时的命令行参数。
    # 例如：
    #   python cli.py "中国武汉房价" --report_type research_report --tone objective
    #
    # 最终会得到一个 `args` 对象，大致等价于：
    #   args.query == "中国武汉房价"
    #   args.report_type == "research_report"
    #   args.tone == "objective"
    #
    # 也就是：
    # “终端里输入的命令参数” -> “Python 里的结构化对象”
    args = cli.parse_args()

    # `main` 是异步函数，所以通过 asyncio.run 启动事件循环。
    asyncio.run(main(args))
