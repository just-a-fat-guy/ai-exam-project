"""GPT Researcher 的“写作阶段控制层”。

这个文件要解决的问题不是“如何搜资料”，而是：

1. 研究阶段已经拿到了 context，接下来怎样进入写作
2. 最终报告、引言、结论、子主题等写作动作如何组织
3. 写作阶段的日志如何推送给前端

阅读这个文件时，要特别注意它和 `report_generation.py` 的职责分工：

- `writer.py`：偏“控制层/编排层”，负责整理写作参数、决定调用哪类写作动作
- `report_generation.py`：偏“执行层/action 层”，负责真正拼 prompt 并调用 LLM
"""

import json
from typing import Dict, Optional

from ..actions import (
    generate_draft_section_titles,
    generate_report,
    stream_output,
    write_conclusion,
    write_report_introduction,
)
from ..utils.llm import construct_subtopics


class ReportGenerator:
    """写作阶段的核心控制器。

    这个类不负责“做研究”，它只消费研究阶段产出的 context。
    你可以把它理解成 `GPTResearcher.write_report()` 真正委托下去的执行者。

    它主要负责：
    - 组织写报告所需的参数
    - 调用不同的 action 函数写正文、引言、结论
    - 处理子主题、草稿标题等写作相关能力
    - 把写作进度和结果通过 websocket 推给前端
    """

    def __init__(self, researcher):
        """初始化写作控制器。

        参数说明：
            researcher:
                上层的 `GPTResearcher` 实例。
                这里面已经包含：
                - query
                - report_type
                - report_source
                - tone
                - websocket
                - cfg
                - role / agent_role
                等写作阶段所需的上下文。
        """
        self.researcher = researcher

        # 先把“几乎所有写作动作都会共用”的参数抽出来，
        # 后面写正文、写引言、写结论时都可以在此基础上补充个别字段。
        self.research_params = {
            "query": self.researcher.query,
            "agent_role_prompt": self.researcher.cfg.agent_role or self.researcher.role,
            "report_type": self.researcher.report_type,
            "report_source": self.researcher.report_source,
            "tone": self.researcher.tone,
            "websocket": self.researcher.websocket,
            "cfg": self.researcher.cfg,
            "headers": self.researcher.headers,
        }

    async def write_report(self, existing_headers: list = [], relevant_written_contents: list = [], ext_context=None, custom_prompt="", available_images: list = None) -> str:
        """写整篇报告正文。

        参数说明：
            existing_headers:
                已经写过的标题列表，主要用于 subtopic_report 等场景，
                避免新写出的标题和已有结构重复。
            relevant_written_contents:
                已经写好的相关内容片段，常用于子主题续写或分段写作时保持连贯性。
            ext_context:
                外部显式传入的上下文；如果提供，就优先使用它，而不是
                `self.researcher.context`。
            custom_prompt:
                调用方自定义的 prompt。通常用于覆盖默认报告提示词。
            available_images:
                研究阶段预生成好的图片信息列表；如果存在，会一起传给
                `generate_report()` 供模型在报告中嵌入图片。

        返回值：
            str:
                最终生成的整篇报告正文。

        这是写作阶段最重要的方法。它主要做四件事：
        1. 把研究图片、上下文、角色 prompt 等写作要素整理好
        2. 根据 report_type 决定是否补充 subtopic 特有参数
        3. 调用 action 层的 `generate_report()`
        4. 对空报告或异常做显式失败处理
        """
        available_images = available_images or []
        
        # 先把研究阶段挑出来的图片发给前端。
        # 这类图片通常是从网页中抓出来、后续可在界面中展示的研究图片，
        # 不一定等于 `available_images` 里的预生成插图。
        research_images = self.researcher.get_research_images()
        if research_images:
            await stream_output(
                "images",
                "selected_images",
                json.dumps(research_images),
                self.researcher.websocket,
                True,
                research_images
            )

        # 优先使用调用方传入的 ext_context；否则退回研究阶段内部 context。
        context = ext_context or self.researcher.context
        
        # 如果已有预生成图片，先告诉前端当前写作阶段可用多少张图片。
        if available_images and self.researcher.verbose:
            await stream_output(
                "logs",
                "images_available",
                f"🖼️ {len(available_images)} pre-generated images available for embedding",
                self.researcher.websocket,
            )
        
        # 写报告正式开始前，给前端打一条明确日志。
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_report",
                f"✍️ Writing report for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # 基于初始化时准备好的通用参数复制一份，避免直接修改共享字典。
        report_params = self.research_params.copy()

        # 如果初始化时还没有 agent_role_prompt，这里再兜底补一次。
        if not report_params["agent_role_prompt"]:
            report_params["agent_role_prompt"] = self.researcher.cfg.agent_role or self.researcher.role

        # 写正文一定需要 context；custom_prompt / available_images 则是可选增强输入。
        report_params["context"] = context
        report_params["custom_prompt"] = custom_prompt
        report_params["available_images"] = available_images

        if self.researcher.report_type == "subtopic_report":
            # 子主题报告需要附带“主问题”和“已有结构”，
            # 否则模型不知道自己是在整份大报告的哪个分支下续写。
            report_params.update({
                "main_topic": self.researcher.parent_query,
                "existing_headers": existing_headers,
                "relevant_written_contents": relevant_written_contents,
                "cost_callback": self.researcher.add_costs,
            })
        else:
            # 普通报告只需要成本回调即可。
            report_params["cost_callback"] = self.researcher.add_costs

        try:
            # 真正的 prompt 选择与 LLM 调用发生在 action 层的 generate_report()。
            report = await generate_report(**report_params, **self.researcher.kwargs)
        except Exception as exc:
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "report_failed",
                    f"❌ Failed to write report for '{self.researcher.query}': {exc}",
                    self.researcher.websocket,
                )
            raise

        # 空字符串也视为失败。
        # 这是因为某些 OpenAI-compatible provider 可能 HTTP 成功，
        # 但最终没有返回可用正文。
        if not report or not report.strip():
            error = RuntimeError(f"Empty report generated for '{self.researcher.query}'")
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "report_failed",
                    f"❌ Failed to write report for '{self.researcher.query}': empty response",
                    self.researcher.websocket,
                )
            raise error

        # 只有拿到了非空正文，才对前端声明“报告写完了”。
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "report_written",
                f"📝 Report written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return report

    async def write_report_conclusion(self, report_content: str) -> str:
        """单独生成报告结论。

        参数说明：
            report_content:
                报告正文内容。结论会基于这份正文进行归纳和收束。

        返回值：
            str:
                生成出来的结论文本。

        这个方法通常在需要把“正文”和“结论”拆开控制时使用。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_conclusion",
                f"✍️ Writing conclusion for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # 结论生成不直接在本类里拼 prompt，而是交给 action 层统一处理。
        conclusion = await write_conclusion(
            query=self.researcher.query,
            context=report_content,
            config=self.researcher.cfg,
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            cost_callback=self.researcher.add_costs,
            websocket=self.researcher.websocket,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "conclusion_written",
                f"📝 Conclusion written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return conclusion

    async def write_introduction(self):
        """单独生成报告引言。

        返回值：
            str:
                生成出来的引言文本。

        引言通常会基于：
        - 当前 query
        - 研究阶段已经得到的整体 context
        - 当前 agent role
        来写。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_introduction",
                f"✍️ Writing introduction for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # 引言生成同样走 action 层，保持和正文/结论一致的调用风格。
        introduction = await write_report_introduction(
            query=self.researcher.query,
            context=self.researcher.context,
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            config=self.researcher.cfg,
            websocket=self.researcher.websocket,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "introduction_written",
                f"📝 Introduction written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return introduction

    async def get_subtopics(self):
        """为当前研究主题生成子主题列表。

        返回值：
            list:
                模型生成出来的子主题列表。

        这个动作通常用于：
        - detailed report
        - subtopic 拆分
        - 后续分段写作
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_subtopics",
                f"🌳 Generating subtopics for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # construct_subtopics 会消费 query + context，并结合 prompt_family 生成结构化子主题。
        subtopics = await construct_subtopics(
            task=self.researcher.query,
            data=self.researcher.context,
            config=self.researcher.cfg,
            subtopics=self.researcher.subtopics,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subtopics_generated",
                f"📊 Subtopics generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return subtopics

    async def get_draft_section_titles(self, current_subtopic: str):
        """为某个子主题生成草稿级别的章节标题。

        参数说明：
            current_subtopic:
                当前正在处理的子主题。

        返回值：
            list[str]:
                模型给出的章节标题列表。

        常见用途：
        - 在真正开始写正文前先粗拟一个章节结构
        - 帮助 detailed report / 子主题报告形成更稳定的层次
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_draft_sections",
                f"📑 Generating draft section titles for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # 章节标题依然属于“写作辅助动作”，因此放在 writer.py 里统一管理。
        draft_section_titles = await generate_draft_section_titles(
            query=self.researcher.query,
            current_subtopic=current_subtopic,
            context=self.researcher.context,
            role=self.researcher.cfg.agent_role or self.researcher.role,
            websocket=self.researcher.websocket,
            config=self.researcher.cfg,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "draft_sections_generated",
                f"🗂️ Draft section titles generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return draft_section_titles
