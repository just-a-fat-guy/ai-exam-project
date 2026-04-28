"""研究角色选择模块。

这个文件的职责非常聚焦：
不是去“写报告”，也不是去“搜资料”，而是在研究开始前先回答一个问题：

    这个任务应该由什么类型的研究 agent 来处理？

在 GPT Researcher 里，agent 并不是一个真正独立运行的多智能体进程。
这里的 `agent` 更接近“研究角色设定”：

- 给当前任务起一个角色名，例如 Finance Agent / Travel Agent
- 生成一段 `agent_role_prompt`
- 后续研究规划、报告写作都会复用这段角色提示词

所以这个文件的本质是：

```text
query -> 让 LLM 选择研究角色 -> 返回 (server, agent_role_prompt)
```
"""

import json
import logging
import re

import json_repair

from ..prompts import PromptFamily
from ..utils.llm import create_chat_completion

logger = logging.getLogger(__name__)


async def choose_agent(
    query,
    cfg,
    parent_query=None,
    cost_callback: callable = None,
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
):
    """自动选择当前任务对应的研究角色。

    参数说明：
        query:
            当前问题。它可能是用户的原始主问题，也可能是某个子主题问题。
        cfg:
            配置对象。这里主要会用到：
            - `smart_llm_model`
            - `smart_llm_provider`
            - `llm_kwargs`
        parent_query:
            父问题。在研究子主题时，单看子问题可能上下文不够，因此会把
            `parent_query + query` 拼起来交给模型，帮助它做更准确的角色判断。
        cost_callback:
            成本统计回调，用于累计这次模型调用的费用。
        headers:
            预留参数，当前函数本体不直接使用。
        prompt_family:
            当前生效的 prompt family。它提供 `auto_agent_instructions()`，
            用来告诉模型应该按什么 JSON 格式返回 agent 信息。
        **kwargs:
            继续透传给底层 LLM 调用的附加参数。

    Returns:
        tuple[str, str]:
            返回 `(agent_name, agent_role_prompt)`。

    这一步是整个项目里一个很典型的“LLM 决策点”：
    - 输入是任务描述
    - 输出是角色设定
    - 后续研究和写作阶段都会复用这个角色 prompt
    """
    # 如果当前研究的是某个子问题，就把父问题一并拼进去。
    # 这样模型不会只看到一个过窄的片段，而是能结合主任务一起判断角色。
    query = f"{parent_query} - {query}" if parent_query else f"{query}"
    # 提前定义 response，确保即使 create_chat_completion 或 json.loads 出错，
    # 后面的错误处理函数也能拿到原始返回值做修复尝试。
    response = None

    try:
        # 这里的调用结构很简单：
        # - system: 给模型一段“你应该如何选择 agent，并按什么 JSON 返回”的规则
        # - user: 给模型当前任务
        response = await create_chat_completion(
            model=cfg.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{prompt_family.auto_agent_instructions()}"},
                {"role": "user", "content": f"task: {query}"},
            ],
            temperature=0.15,
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )

        # 理想情况下，模型会严格返回一个 JSON：
        # {
        #   "server": "...",
        #   "agent_role_prompt": "..."
        # }
        agent_dict = json.loads(response)
        return agent_dict["server"], agent_dict["agent_role_prompt"]

    except Exception:
        # 这里不直接抛错，而是进入容错逻辑。
        # 原因很简单：agent 选择属于“增强项”，失败了也不值得让整个研究流程中断。
        return await handle_json_error(response)


async def handle_json_error(response: str | None):
    """处理 agent 选择阶段的 JSON 解析失败。

    这个函数的目标不是“严格校验 JSON”，而是尽量把模型输出救回来。
    它采用三层回退策略：

    1. 先用 `json_repair` 修复不规范 JSON
    2. 再用正则从文本里抽出疑似 JSON 片段
    3. 最后如果还不行，就回退到默认 agent

    参数说明：
        response:
            模型原始输出文本。

    返回值：
        tuple[str, str]:
            `(agent_name, agent_role_prompt)`。

    这个设计非常实用：
    agent 选择不是高风险结构化输出，不值得因为一点 JSON 格式问题就让系统完全失败。
    """
    try:
        # 第一层回退：使用 json_repair 修复轻微格式错误。
        # 例如多余逗号、引号不规范、少括号等常见问题。
        agent_dict = json_repair.loads(response)
        if agent_dict.get("server") and agent_dict.get("agent_role_prompt"):
            return agent_dict["server"], agent_dict["agent_role_prompt"]
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.warning(
            f"Failed to parse agent JSON with json_repair: {error_type}: {error_msg}",
            exc_info=True
        )
        if response:
            logger.debug(f"LLM response that failed to parse: {response[:500]}...")

    # 第二层回退：如果整个字符串不是合法 JSON，
    # 但里面嵌着一段 `{...}`，就先抽出来再尝试 decode。
    json_string = extract_json_with_regex(response)
    if json_string:
        try:
            json_data = json.loads(json_string)
            return json_data["server"], json_data["agent_role_prompt"]
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to decode JSON from regex extraction: {str(e)}",
                exc_info=True
            )

    # 第三层回退：给出一个稳定的默认 agent。
    # 这意味着即便“自动角色选择”失效，整个研究系统仍然可以继续工作。
    logger.info("No valid JSON found in LLM response. Falling back to default agent.")
    return "Default Agent", (
        "You are an AI critical thinker research assistant. Your sole purpose is to write well written, "
        "critically acclaimed, objective and structured reports on given text."
    )


def extract_json_with_regex(response: str | None) -> str | None:
    """用正则从模型输出里提取第一段 JSON 对象。

    参数说明：
        response:
            模型返回的原始字符串。

    返回值：
        str | None:
            如果找到形如 `{...}` 的片段，就返回该字符串；否则返回 `None`。

    这个函数很朴素，但很有价值。
    因为很多模型在返回结构化内容时会夹杂解释文本，例如：

    ```text
    Sure, here is the JSON:
    { ... }
    ```

    这时候直接 `json.loads(response)` 会失败，但把中间的 JSON 片段抽出来就能继续解析。
    """
    if not response:
        return None
    json_match = re.search(r"{.*?}", response, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return None
