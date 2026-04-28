import asyncio
from typing import List, Dict, Any
from ..config.config import Config
from ..utils.llm import create_chat_completion
from ..utils.logger import get_formatted_logger
from ..prompts import PromptFamily, get_prompt_by_report_type
from ..utils.enum import Tone

logger = get_formatted_logger()


async def _send_report_to_websocket(report: str, websocket) -> None:
    """把非流式生成出来的完整报告一次性推给前端。

    参数说明：
        report:
            已经完整生成好的报告正文。
        websocket:
            前端连接对象；如果没有前端连接，这里会直接跳过。

    这个辅助函数主要服务于 fallback 场景：
    某些 provider 在 streaming 模式下可能拿不到有效文本，
    但在 non-streaming 模式下可以成功返回完整内容。
    """
    if websocket is None or not report:
        return
    await websocket.send_json({"type": "report", "output": report})


async def write_report_introduction(
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """生成报告引言。

    参数说明：
        query:
            当前研究问题。
        context:
            研究阶段整理好的上下文。
        agent_role_prompt:
            当前 agent 的角色提示词。它通常作为 system prompt 使用，
            用来规定“以什么身份、什么风格”来写引言。
        config:
            全局配置对象，里面有模型、token 限制、语言等配置。
        websocket:
            前端流式输出连接；如果存在，会边生成边推送引言内容。
        cost_callback:
            成本统计回调，用来累计模型调用成本。
        prompt_family:
            当前生效的 prompt family，不同 family 可覆盖引言 prompt 模板。

    返回值：
        str:
            生成出来的引言文本。
    """
    try:
        # 这里的 prompt 不是手写字符串，而是交给 prompt_family 统一生成。
        introduction = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},
                {"role": "user", "content": prompt_family.generate_report_introduction(
                    question=query,
                    research_summary=context,
                    language=config.language
                )},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return introduction
    except Exception as e:
        # 这里选择“记录日志 + 返回空串”，而不是直接抛异常。
        # 因为引言通常不是主流程唯一产物，调用方可以自行决定是否继续。
        logger.error(f"Error in generating report introduction: {e}")
    return ""


async def write_conclusion(
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """生成报告结论。

    参数说明与 `write_report_introduction()` 基本一致，不同点在于：
        - 输入上下文这里通常是“正文内容”
        - prompt 使用的是 `generate_report_conclusion()`

    返回值：
        str:
            生成出来的结论文本。
    """
    try:
        conclusion = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},
                {
                    "role": "user",
                    "content": prompt_family.generate_report_conclusion(query=query,
                                                                        report_content=context,
                                                                        language=config.language),
                },
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return conclusion
    except Exception as e:
        # 和引言一样，结论生成失败时先返回空串，让上层决定怎么处理。
        logger.error(f"Error in writing conclusion: {e}")
    return ""


async def summarize_url(
    url: str,
    content: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    **kwargs
) -> str:
    """对单个 URL 的内容做摘要。

    参数说明：
        url:
            当前内容对应的网址。
        content:
            已抓取出来的网页正文。
        role:
            角色提示词，用于约束摘要风格。
        config / websocket / cost_callback:
            与其他 LLM 调用函数含义一致。

    返回值：
        str:
            生成出来的摘要文本。

    这是一个更细粒度的写作辅助函数，不直接参与“整篇报告生成”主链，
    但适合做来源摘要、局部内容提炼等动作。
    """
    try:
        summary = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},
                {"role": "user", "content": f"Summarize the following content from {url}:\n\n{content}"},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return summary
    except Exception as e:
        logger.error(f"Error in summarizing URL: {e}")
    return ""


async def generate_draft_section_titles(
    query: str,
    current_subtopic: str,
    context: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """为某个子主题生成草稿章节标题。

    参数说明：
        query:
            总问题。
        current_subtopic:
            当前子主题。
        context:
            当前可用的研究上下文。
        role:
            角色提示词。
        config / websocket / cost_callback / prompt_family:
            与其他写作辅助函数含义一致。

    返回值：
        List[str]:
            模型生成的章节标题列表。

    注意：
        这里返回的是“草稿标题”，并不保证最终一定原样进入报告。
    """
    try:
        section_titles = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},
                {"role": "user", "content": prompt_family.generate_draft_titles_prompt(
                    current_subtopic, query, context)},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=None,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        # 当前实现假设模型用换行分隔标题，因此这里直接 split。
        return section_titles.split("\n")
    except Exception as e:
        logger.error(f"Error in generating draft section titles: {e}")
    return []


async def generate_report(
    query: str,
    context,
    agent_role_prompt: str,
    report_type: str,
    tone: Tone,
    report_source: str,
    websocket,
    cfg,
    main_topic: str = "",
    existing_headers: list = [],
    relevant_written_contents: list = [],
    cost_callback: callable = None,
    custom_prompt: str = "", # This can be any prompt the user chooses with the context
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    available_images: list = None,
    **kwargs
):
    """生成最终报告正文。

    参数说明：
        query:
            当前问题。
        context:
            研究阶段整理出来的上下文，通常是整篇报告最核心的输入。
        agent_role_prompt:
            角色提示词，通常作为 system prompt 使用。
        report_type:
            报告类型，决定选用哪套 prompt 模板。
        tone:
            报告语气。
        report_source:
            数据来源类型，例如 web / local / hybrid。
        websocket:
            前端流式输出连接。
        cfg:
            配置对象，包含语言、token 限制、模型选择等。
        main_topic:
            主问题，仅在 subtopic_report 等场景里需要。
        existing_headers:
            已有标题列表，用于子主题报告避免重复结构。
        relevant_written_contents:
            已写好的相关内容片段，用于续写保持衔接。
        cost_callback:
            成本统计回调。
        custom_prompt:
            调用方自定义的 prompt；如果提供，会优先覆盖默认报告 prompt。
        headers:
            额外 headers，目前主要是透传参数，函数本体不直接使用。
        prompt_family:
            当前生效的 prompt family。
        available_images:
            研究阶段已经准备好的图片信息列表，可嵌入报告。

    返回值：
        str:
            最终报告正文。

    这是“写报告”主链里真正触发 LLM 的核心函数。
    你可以把它理解成：
        1. 先根据 report_type 选 prompt
        2. 再构造 messages
        3. 先尝试 streaming 生成
        4. streaming 失败时，再 fallback 到 non-streaming
    """
    available_images = available_images or []

    # 先根据报告类型选择对应的 prompt 生成函数。
    # 例如 research_report、subtopic_report、deep_research 会走不同模板。
    generate_prompt = get_prompt_by_report_type(report_type, prompt_family)
    report = ""

    if report_type == "subtopic_report":
        # 子主题报告需要额外知道：
        # - 主问题是什么
        # - 已有哪些标题
        # - 已写过哪些内容
        content = f"{generate_prompt(query, existing_headers, relevant_written_contents, main_topic, context, report_format=cfg.report_format, tone=tone, total_words=cfg.total_words, language=cfg.language)}"
    elif custom_prompt:
        # 如果调用方显式给了 custom_prompt，就优先用它覆盖默认报告模板。
        content = f"{custom_prompt}\n\nContext: {context}"
    else:
        # 普通报告场景：根据 query + context + report_source + tone 等生成默认 prompt。
        content = f"{generate_prompt(query, context, report_source, report_format=cfg.report_format, tone=tone, total_words=cfg.total_words, language=cfg.language)}"
    
    # 如果研究阶段已经准备好了图片，这里会把图片清单追加进 prompt。
    # 这样模型在写报告时就能直接嵌入这些图片的 markdown 语法。
    if available_images:
        images_info = "\n".join([
            f"- Image {i+1}: ![{img.get('title', img.get('alt_text', 'Illustration'))}]({img['url']}) - {img.get('section_hint', 'General')}"
            for i, img in enumerate(available_images)
        ])
        content += f"""

AVAILABLE IMAGES:
You have the following pre-generated images available. Embed them in relevant sections of your report using the exact markdown syntax provided:

{images_info}

Place each image on its own line after the relevant section header or paragraph. Use all available images where they add value to the content."""

    # 首选消息结构：system 放角色提示词，user 放具体任务内容。
    primary_messages = [
        {"role": "system", "content": f"{agent_role_prompt}"},
        {"role": "user", "content": content},
    ]

    # 兼容性回退消息结构：把 role prompt 和任务内容合并进 user。
    # 某些 provider 或模型对 system prompt 的处理不稳定，这种写法更保守。
    fallback_messages = [
        {"role": "user", "content": f"{agent_role_prompt}\n\n{content}"},
    ]

    last_exception: Exception | None = None

    # 第一优先级：直接流式生成。
    # 这样前端可以边生成边展示，交互体验最好。
    for messages in (primary_messages, fallback_messages):
        try:
            report = await create_chat_completion(
                model=cfg.smart_llm_model,
                messages=messages,
                temperature=0.35,
                llm_provider=cfg.smart_llm_provider,
                stream=True,
                websocket=websocket,
                max_tokens=cfg.smart_token_limit,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
            if report and report.strip():
                return report
        except Exception as exc:
            last_exception = exc
            logger.warning(f"Streaming report generation failed, falling back: {exc}")

    # 第二优先级：非流式回退。
    # 有些 OpenAI-compatible provider 会出现：
    # - HTTP 请求成功
    # - 但 streaming 没有拿到有效正文
    # 这时改用 non-streaming 反而能取到完整结果。
    for messages in (primary_messages, fallback_messages):
        try:
            report = await create_chat_completion(
                model=cfg.smart_llm_model,
                messages=messages,
                temperature=0.35,
                llm_provider=cfg.smart_llm_provider,
                stream=False,
                websocket=None,
                max_tokens=cfg.smart_token_limit,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
            if report and report.strip():
                # 虽然这轮不是流式拿到的，但前端仍然需要看到最终正文，
                # 因此这里补一次“整块推送”。
                await _send_report_to_websocket(report, websocket)
                return report
        except Exception as exc:
            last_exception = exc
            logger.warning(f"Non-streaming report fallback failed: {exc}")

    # 两轮都失败时，显式抛出错误，让上层能区分“空报告”和“真正失败”。
    raise RuntimeError("Failed to generate report from LLM") from last_exception
