"""LLM 调用工具层。

这个文件位于“生成能力层”和“底层 provider”之间，主要做三件事：
1. 统一不同 LLM provider 的调用入口
2. 处理通用参数，例如 temperature / max_tokens / reasoning_effort
3. 处理重试、空响应、成本统计等运行时细节

因此，这一层不关心“要写什么 prompt”，那是 `prompts.py` 的职责；
它关心的是“拿着已经准备好的 messages，怎样稳定地把模型调起来”。
"""
from __future__ import annotations

import logging
import os
from typing import Any
import asyncio

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from gpt_researcher.llm_provider.generic.base import (
    NO_SUPPORT_TEMPERATURE_MODELS,
    SUPPORT_REASONING_EFFORT_MODELS,
    ReasoningEfforts,
)

from ..prompts import PromptFamily
from .costs import estimate_llm_cost
from .validators import Subtopics


def get_llm(llm_provider: str, **kwargs):
    """获取统一封装后的 LLM provider 实例。

    Args:
        llm_provider:
            provider 名称，例如 `openai`、`anthropic`、`ollama`。
        **kwargs:
            传给具体 provider 的额外参数，通常包括 model、temperature、
            max_tokens、reasoning_effort 等。

    Returns:
        GenericLLMProvider:
            已按指定 provider 配置好的统一适配对象。
    """
    from gpt_researcher.llm_provider import GenericLLMProvider
    return GenericLLMProvider.from_provider(llm_provider, **kwargs)


async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        **kwargs
) -> str:
    """统一创建一次聊天补全请求。

    虽然函数名沿用了 chat completion，但这里并不只服务 OpenAI。
    调用方只需要传入 provider 名称和 messages，底层会通过通用 provider
    适配层去调用具体模型。

    Args:
        messages:
            标准 chat messages 列表，通常由 system/user/assistant 消息组成。
        model:
            具体模型名。这里不能为空，因为项目允许多 provider、多模型切换。
        temperature:
            采样温度。并不是所有模型都支持，因此后面会按模型能力判断是否透传。
        max_tokens:
            最大输出 token 数。
        llm_provider:
            底层 provider 名称。
        stream:
            是否采用流式输出。如果为 True，provider 可能会边生成边向 websocket 推送。
        websocket:
            当前请求对应的 websocket 连接。只有在流式场景下才真正有意义。
        llm_kwargs:
            额外 provider 参数，通常来自项目配置，例如自定义 base_url 或其他扩展参数。
        cost_callback:
            成本统计回调。成功拿到响应后会估算本次调用成本并回调。
        reasoning_effort:
            推理模型的 effort 档位，仅对支持该特性的模型生效。
        **kwargs:
            继续透传给具体 provider 的附加参数。

    Returns:
        str:
            模型返回的最终文本。

    行为说明：
        - 流式 + websocket 场景下，默认只尝试 1 次，避免前端被重复推送内容
        - 非流式场景下，默认最多重试 10 次
        - 如果 provider 返回空文本，也视为失败并进入重试逻辑
    """
    max_attempts_override = kwargs.pop("max_attempts", None)
    retry_delay_cap = kwargs.pop("retry_delay_cap", 8)

    # validate input
    if model is None:
        raise ValueError("Model cannot be None")
    if max_tokens is not None and max_tokens > 32001:
        raise ValueError(
            f"Max tokens cannot be more than 32,000, but got {max_tokens}")

    # 先组装 provider 初始化参数。
    # 这里做的是“通用参数到具体 provider 参数”的一次映射。
    provider_kwargs = {'model': model}

    if llm_kwargs:
        provider_kwargs.update(llm_kwargs)

    # reasoning_effort 只对部分推理模型有效，不能无脑透传。
    if model in SUPPORT_REASONING_EFFORT_MODELS:
        provider_kwargs['reasoning_effort'] = reasoning_effort

    # 有些模型不支持 temperature / max_tokens；如果强行传参反而会报错。
    if model not in NO_SUPPORT_TEMPERATURE_MODELS:
        provider_kwargs['temperature'] = temperature
        provider_kwargs['max_tokens'] = max_tokens
    else:
        provider_kwargs['temperature'] = None
        provider_kwargs['max_tokens'] = None

    if llm_provider == "openai":
        # 项目允许通过 OPENAI_BASE_URL 把 OpenAI 兼容调用重定向到别的网关，
        # 比如 Azure、OpenRouter、豆包兼容接口等。
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        if base_url:
            provider_kwargs['openai_api_base'] = base_url

    provider = get_llm(llm_provider, **provider_kwargs)
    response = ""
    # 流式 + websocket 场景下只尝试一次：
    # 如果重试，很容易让前端重复收到半截内容，体验和状态都不好维护。
    # 非流式则可以更积极地重试。
    max_attempts = 1 if (stream and websocket is not None) else 10
    if max_attempts_override is not None:
        try:
            max_attempts = max(1, int(max_attempts_override))
        except (TypeError, ValueError):
            logging.getLogger(__name__).warning(
                "Invalid max_attempts override %r, falling back to %s",
                max_attempts_override,
                max_attempts,
            )
    last_exception: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            # 真正的 provider 调用发生在这里。
            response = await provider.get_chat_response(
                messages, stream, websocket, **kwargs
            )
        except Exception as exc:
            last_exception = exc
            logging.getLogger(__name__).warning(
                f"LLM request failed (attempt {attempt}/{max_attempts}): {exc}"
            )
            if attempt < max_attempts:
                # 指数退避，避免短时间内把失败请求打满。
                await asyncio.sleep(min(2 ** (attempt - 1), retry_delay_cap))
                continue
            break

        if not response:
            # provider 没抛异常，但也没返回可用文本，这里同样按失败处理。
            last_exception = RuntimeError("Empty response from LLM provider")
            logging.getLogger(__name__).warning(
                f"LLM returned empty response (attempt {attempt}/{max_attempts})"
            )
            if attempt < max_attempts:
                await asyncio.sleep(min(2 ** (attempt - 1), retry_delay_cap))
                continue
            break

        if cost_callback:
            # 这里只做估算统计，不参与主流程控制。
            llm_costs = estimate_llm_cost(str(messages), response)
            cost_callback(llm_costs)

        return response

    logging.error(f"Failed to get response from {llm_provider} API")
    raise RuntimeError(f"Failed to get response from {llm_provider} API") from last_exception


async def construct_subtopics(
    task: str,
    data: str,
    config,
    subtopics: list = [],
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> list:
    """根据主任务和研究数据，生成结构化子主题列表。

    Args:
        task:
            主任务或主主题。
        data:
            当前已经拿到的研究数据，模型会基于这些内容来拆分子主题。
        config: Configuration settings.
        subtopics:
            现有子主题列表，通常用于“给模型一个候选范围或已有上下文”。
        prompt_family:
            当前生效的 prompt family，用来生成子主题 prompt 模板。
        **kwargs:
            透传给 LangChain chain 调用的额外参数。

    Returns:
        list:
            解析后的子主题对象列表；如果失败，则退回原始 `subtopics`。

    这个函数和普通的 `create_chat_completion()` 不同点在于：
        - 它要求模型输出结构化结果
        - 因此这里使用 `PydanticOutputParser`
        - 一旦模型输出格式不合法，解析阶段就会失败
    """
    try:
        # 这里通过 Pydantic 约束输出格式，确保模型返回的是“子主题列表”而不是散文。
        parser = PydanticOutputParser(pydantic_object=Subtopics)

        # 注意：这里的 prompt 是模板，不是最终字符串。
        # 真正调用时，会把 task/data/subtopics/max_subtopics 填进去。
        prompt = PromptTemplate(
            template=prompt_family.generate_subtopics_prompt(),
            input_variables=["task", "data", "subtopics", "max_subtopics"],
            partial_variables={
                "format_instructions": parser.get_format_instructions()},
        )

        # 子主题拆分通常属于“高价值规划动作”，因此默认走 smart_llm。
        provider_kwargs = {'model': config.smart_llm_model}

        if config.llm_kwargs:
            provider_kwargs.update(config.llm_kwargs)

        if config.smart_llm_model in SUPPORT_REASONING_EFFORT_MODELS:
            provider_kwargs['reasoning_effort'] = ReasoningEfforts.High.value
        else:
            provider_kwargs['temperature'] = config.temperature
            provider_kwargs['max_tokens'] = config.smart_token_limit

        provider = get_llm(config.smart_llm_provider, **provider_kwargs)

        model = provider.llm

        # LangChain chain：Prompt -> Model -> Parser
        # 这个顺序很适合“生成结构化输出”的场景。
        chain = prompt | model | parser

        output = await chain.ainvoke({
            "task": task,
            "data": data,
            "subtopics": subtopics,
            "max_subtopics": config.max_subtopics
        }, **kwargs)

        return output

    except Exception as e:
        print("Exception in parsing subtopics : ", e)
        logging.getLogger(__name__).error(f"Exception in parsing subtopics : \n {e}")
        # 出错时退回已有 subtopics，而不是直接中断整个详细报告流程。
        return subtopics
