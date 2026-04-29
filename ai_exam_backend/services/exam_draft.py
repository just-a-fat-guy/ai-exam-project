"""AI 组卷草案服务。

这一层现在承担两档能力：

1. 模板级草案回退
   当题位不允许 AI 出题，或单题 LLM 生成失败时，仍然返回结构完整的草案题目。

2. 真实 LLM 预览出题
   当题位允许 AI 参与时，优先调用当前配置的 SMART_LLM 生成题目级 JSON。

这样做的目标不是一次性把正式考试系统做完，而是先把“题目级生成闭环”真正跑起来，
并且在失败时只影响单题，不让整张试卷一起报废。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from gpt_researcher.config.config import Config
from gpt_researcher.utils.llm import create_chat_completion

from schemas import (
    ExamDraftQuestion,
    ExamDraftSection,
    ExamPaperDraft,
    ExamQualityIssue,
    ExamPaperRequest,
    ExamQuestionOption,
    ExamQuestionRegenerationDiff,
    QuestionType,
    ExamQuestionSnapshot,
)

from .exam_preview import build_exam_paper_preview
from .exam_quality import validate_exam_draft_quality


logger = logging.getLogger(__name__)

QUESTION_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
    "fill_blank": "填空题",
    "short_answer": "简答题",
    "essay": "作文题",
    "calculation": "计算题",
    "case_analysis": "案例分析题",
    "reading_comprehension": "阅读理解题",
    "cloze": "完形填空题",
    "translation": "翻译题",
    "practical": "实践题",
    "composite": "综合题",
}

DIFFICULTY_LABELS = {
    "easy": "基础",
    "medium": "中等",
    "hard": "提高",
}

CHOICE_OPTION_COUNT = {
    QuestionType.SingleChoice.value: 4,
    QuestionType.MultipleChoice.value: 4,
    QuestionType.TrueFalse.value: 2,
}

COMPACT_SOLUTION_TYPES = {
    QuestionType.ShortAnswer.value,
    QuestionType.Calculation.value,
    QuestionType.Composite.value,
}

GENERATION_SUMMARY_PREFIX = "本次草案生成统计："
RAW_RESPONSE_PREVIEW_LIMIT = 600


def _build_paper_id(exam_request: ExamPaperRequest) -> str:
    subject = exam_request.subject.value
    grade = exam_request.grade
    exam_type = exam_request.exam_type
    section_count = len(exam_request.sections)
    return f"draft_{subject}_{grade}_{exam_type}_{section_count}"


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _issue(level: str, code: str, message: str, path: str) -> ExamQualityIssue:
    return ExamQualityIssue(level=level, code=code, message=message, path=path)


def _pick_primary_knowledge_point(slot: dict[str, Any]) -> str:
    points = slot.get("knowledge_points") or []
    return points[0] if points else "核心知识点"


def _get_llm_config() -> Config:
    """读取当前环境配置，供 AI 出题使用。"""

    config_path = os.environ.get("CONFIG_PATH")
    return Config(config_path if config_path and config_path != "default" else None)


def _parse_exam_thinking_payload() -> dict[str, Any] | None:
    """把环境变量里的 thinking 配置转成兼容 ARK 的对象结构。"""

    raw_value = str(os.getenv("AI_EXAM_THINKING", "")).strip()
    if not raw_value:
        return None

    if raw_value.startswith("{"):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            logger.warning("Invalid AI_EXAM_THINKING JSON config: %s", raw_value)
            return None
        return parsed if isinstance(parsed, dict) else None

    return {"type": raw_value.lower()}


def _get_exam_llm_kwargs(cfg: Config, llm_provider: str) -> dict[str, Any] | None:
    """为考试出题链路补充 provider 初始化参数。"""

    llm_kwargs = dict(cfg.llm_kwargs or {})
    thinking_payload = _parse_exam_thinking_payload()
    if llm_provider == "openai" and thinking_payload:
        extra_body = llm_kwargs.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body["thinking"] = thinking_payload
        llm_kwargs["extra_body"] = extra_body
    return llm_kwargs or None


def _get_exam_reasoning_effort(cfg: Config, llm_provider: str) -> str | None:
    """如果已显式控制 thinking，则不再继续传 reasoning_effort。"""

    llm_kwargs = _get_exam_llm_kwargs(cfg, llm_provider) or {}
    extra_body = llm_kwargs.get("extra_body")
    thinking_config = extra_body.get("thinking") if isinstance(extra_body, dict) else None
    if isinstance(thinking_config, dict) and thinking_config.get("type") == "disabled":
        return None
    return cfg.reasoning_effort


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _preview_text(value: Any, *, limit: int = RAW_RESPONSE_PREVIEW_LIMIT) -> str:
    """把原始响应压成便于日志查看的单行预览。"""

    if value is None:
        return "<empty>"
    text = str(value).strip()
    if not text:
        return "<empty>"
    normalized = re.sub(r"\s+", " ", text)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}...<truncated>"


def _log_raw_response(context_label: str, stage: str, response_text: str) -> None:
    logger.info(
        "LLM raw response [%s][%s]: %s",
        context_label,
        stage,
        _preview_text(response_text),
    )


def _format_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return f"{exc.__class__.__name__}: {exc!r}"


async def _emit_progress(
    progress_callback,
    *,
    stage: str,
    message: str,
    level: str = "info",
    metadata: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    maybe_awaitable = progress_callback(
        {
            "stage": stage,
            "message": message,
            "level": level,
            "metadata": metadata or {},
            "progress": progress or {},
        }
    )
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


def _find_balanced_json_object(text: str) -> str | None:
    """从混合文本中尽量截出第一个平衡的大括号 JSON 对象。"""

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _extract_json_payload(text: str) -> dict[str, Any]:
    """从 LLM 输出里提取 JSON 对象。"""

    stripped = text.strip()

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    json_str = _find_balanced_json_object(stripped)
    if not json_str:
        raise ValueError("LLM output does not contain a JSON object")

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    
    try:
        json_str_clean = re.sub(r'\\', '', json_str)
        parsed = json.loads(json_str_clean)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    
    try:
        import ast

        parsed = ast.literal_eval(json_str)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    raise ValueError("LLM output does not contain a valid JSON object")


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"[\n,，;；]", value)
        return [part.strip() for part in parts if part.strip()]
    return [str(value).strip()]


def _normalize_reference_answer(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if re.fullmatch(r"[A-Z](?:\s*[,/、]\s*[A-Z])+", stripped):
            parts = re.split(r"\s*[,/、]\s*", stripped)
            return [part for part in parts if part]
        return stripped
    return str(value)


def _requires_compact_solution_mode(question_type: str) -> bool:
    return question_type in COMPACT_SOLUTION_TYPES


def _trim_compact_text(value: str | None, *, max_chars: int) -> str | None:
    if not value:
        return value

    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) <= max_chars:
        return normalized

    for separator in ["；", "。", "，", ",", "\n"]:
        index = normalized.rfind(separator, 0, max_chars)
        if index >= max_chars // 2:
            return normalized[: index + 1].strip()

    return f"{normalized[:max_chars].rstrip()}..."


def _compact_reference_answer(value: str | list[str] | None) -> str | list[str] | None:
    if value is None:
        return None

    if isinstance(value, list):
        compact_items = [
            _trim_compact_text(str(item), max_chars=40)
            for item in value[:4]
            if _trim_compact_text(str(item), max_chars=40)
        ]
        return compact_items or None

    text = _trim_compact_text(value, max_chars=140)
    if not text:
        return None

    parts = [
        segment.strip()
        for segment in re.split(r"[；;\n]", text)
        if segment.strip()
    ]
    if len(parts) > 1:
        return parts[:3]
    return text


def _pick_first_present(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def _normalize_question_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """把不同模型常见的字段别名归一到当前后端期望的结构。"""

    raw_options = _pick_first_present(payload, ["options", "choices", "choice_list", "选项", "备选项"])
    if isinstance(raw_options, dict):
        raw_options = [
            {"label": str(label).strip(), "content": content}
            for label, content in raw_options.items()
        ]

    normalized = dict(payload)
    normalized["stem"] = _string_or_none(
        _pick_first_present(
            payload,
            ["stem", "question_stem", "question", "content", "prompt", "题干", "题目", "题目内容"],
        )
    )
    normalized["options"] = raw_options or []
    normalized["reference_answer"] = _normalize_reference_answer(
        _pick_first_present(
            payload,
            ["reference_answer", "answer", "correct_answer", "答案", "参考答案", "正确答案"],
        )
    )
    normalized["explanation"] = _string_or_none(
        _pick_first_present(
            payload,
            ["explanation", "analysis", "reasoning", "解析", "参考解析", "答案解析"],
        )
    )
    normalized["knowledge_points"] = _list_of_strings(
        _pick_first_present(
            payload,
            ["knowledge_points", "knowledgePoints", "points", "知识点", "考点"],
        )
    )
    return normalized


def _build_preview_stem(
    exam_request: ExamPaperRequest,
    section: dict[str, Any],
    slot: dict[str, Any],
) -> str:
    question_type_label = QUESTION_TYPE_LABELS.get(
        slot["question_type"],
        slot["question_type"],
    )
    knowledge_point = _pick_primary_knowledge_point(slot)
    difficulty = slot.get("difficulty")
    difficulty_label = DIFFICULTY_LABELS.get(difficulty, "常规")

    return (
        f"【预览草案】请围绕“{knowledge_point}”设计一道{difficulty_label}{question_type_label}。"
        f" 该题属于《{exam_request.paper_title}》中的“{section['section_name']}”部分，"
        "当前仅用于确认题位结构、知识点覆盖和审核流程，后续可替换成真实题库抽题结果或 LLM 生成结果。"
    )


def _build_preview_options(
    question_type: str,
    knowledge_point: str,
) -> list[ExamQuestionOption]:
    if question_type == QuestionType.SingleChoice.value:
        return [
            ExamQuestionOption(label="A", content=f"{knowledge_point} 的基础判断项", is_correct=True),
            ExamQuestionOption(label="B", content=f"{knowledge_point} 的常见干扰项一", is_correct=False),
            ExamQuestionOption(label="C", content=f"{knowledge_point} 的常见干扰项二", is_correct=False),
            ExamQuestionOption(label="D", content=f"{knowledge_point} 的常见干扰项三", is_correct=False),
        ]

    if question_type == QuestionType.MultipleChoice.value:
        return [
            ExamQuestionOption(label="A", content=f"{knowledge_point} 的正确要点一", is_correct=True),
            ExamQuestionOption(label="B", content=f"{knowledge_point} 的正确要点二", is_correct=True),
            ExamQuestionOption(label="C", content=f"{knowledge_point} 的高频误区一", is_correct=False),
            ExamQuestionOption(label="D", content=f"{knowledge_point} 的高频误区二", is_correct=False),
        ]

    if question_type == QuestionType.TrueFalse.value:
        return [
            ExamQuestionOption(label="A", content="正确", is_correct=True),
            ExamQuestionOption(label="B", content="错误", is_correct=False),
        ]

    return []


def _build_reference_answer(question_type: str, knowledge_point: str) -> str | list[str] | None:
    if question_type == QuestionType.SingleChoice.value:
        return "A"
    if question_type == QuestionType.MultipleChoice.value:
        return ["A", "B"]
    if question_type == QuestionType.TrueFalse.value:
        return "正确"
    if question_type == QuestionType.FillBlank.value:
        return f"{knowledge_point} 的关键结论"
    if question_type in {
        QuestionType.ShortAnswer.value,
        QuestionType.Essay.value,
        QuestionType.Calculation.value,
        QuestionType.CaseAnalysis.value,
        QuestionType.ReadingComprehension.value,
        QuestionType.Cloze.value,
        QuestionType.Translation.value,
        QuestionType.Practical.value,
        QuestionType.Composite.value,
    }:
        return f"围绕 {knowledge_point} 的参考作答要点"
    return None


def _build_explanation(question_type: str, knowledge_point: str) -> str:
    question_type_label = QUESTION_TYPE_LABELS.get(question_type, question_type)
    return (
        f"这是一道{question_type_label}预览草案。正式生成时需要结合“{knowledge_point}”"
        "补齐真实题干、标准答案和解析链路；当前解析仅用于确认输出结构。"
    )


def _build_quality_flags(slot: dict[str, Any]) -> list[str]:
    flags = ["preview_only"]
    if slot.get("score") is None:
        flags.append("missing_score")
    if not slot.get("knowledge_points"):
        flags.append("missing_knowledge_points")
    return flags


def _build_quality_flags_from_question(question: ExamDraftQuestion) -> list[str]:
    flags = []
    if question.score is None:
        flags.append("missing_score")
    if not question.knowledge_points:
        flags.append("missing_knowledge_points")
    return flags


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_question_snapshot(question: ExamDraftQuestion) -> ExamQuestionSnapshot:
    return ExamQuestionSnapshot(
        stem=question.stem,
        options=[option.model_copy(deep=True) for option in question.options],
        reference_answer=question.reference_answer,
        explanation=question.explanation,
        knowledge_points=list(question.knowledge_points),
    )


def _build_regeneration_diff(
    previous_question: ExamDraftQuestion,
    current_question: ExamDraftQuestion,
    *,
    review_comment: str | None = None,
) -> ExamQuestionRegenerationDiff:
    return ExamQuestionRegenerationDiff(
        previous=_build_question_snapshot(previous_question),
        current=_build_question_snapshot(current_question),
        comment=review_comment,
        regenerated_at=_now_iso(),
    )


def _build_template_question(
    exam_request: ExamPaperRequest,
    section: dict[str, Any],
    slot: dict[str, Any],
    *,
    draft_status: str = "template_preview",
    extra_flags: list[str] | None = None,
) -> ExamDraftQuestion:
    knowledge_point = _pick_primary_knowledge_point(slot)
    quality_flags = _build_quality_flags(slot)
    if extra_flags:
        quality_flags.extend(extra_flags)

    return ExamDraftQuestion(
        question_id=f"Q-{slot['slot_id']}",
        slot_id=slot["slot_id"],
        order=slot["global_slot_index"],
        section_order=section["section_order"],
        section_name=section["section_name"],
        question_type=slot["question_type"],
        difficulty=slot.get("difficulty"),
        score=slot.get("score"),
        source_strategy=slot["source_strategy"],
        draft_status=draft_status,
        knowledge_points=slot.get("knowledge_points") or [],
        stem=_build_preview_stem(exam_request, section, slot),
        options=_build_preview_options(slot["question_type"], knowledge_point),
        reference_answer=_build_reference_answer(slot["question_type"], knowledge_point),
        explanation=_build_explanation(slot["question_type"], knowledge_point),
        constraints=slot.get("constraints") or [],
        quality_flags=quality_flags,
    )


def _build_regeneration_prompt(
    paper: ExamPaperDraft,
    section: ExamDraftSection,
    question: ExamDraftQuestion,
    review_comment: str | None,
) -> list[dict[str, str]]:
    """为单题重生成构造 messages。

    和首次出题不同，这里会把“上一版题目”和“老师的驳回原因”一并交给模型，
    让它明确知道这不是首次生成，而是定向改题。
    """

    question_type_label = QUESTION_TYPE_LABELS.get(question.question_type, question.question_type)
    difficulty_label = DIFFICULTY_LABELS.get(question.difficulty, "常规")
    include_answers = bool(paper.generation_policy.get("include_answers", True))
    include_explanations = bool(paper.generation_policy.get("include_explanations", True))
    contract = _build_question_output_contract(
        question_type=question.question_type,
        knowledge_points=question.knowledge_points or ["核心知识点"],
        include_answers=include_answers,
        include_explanations=include_explanations,
    )
    paper_level_guidance = list(getattr(paper, "paper_level_guidance", []) or [])
    recent_feedback_memory = list(getattr(paper, "feedback_history", []) or [])[-3:]

    user_prompt = f"""
请你重生成 1 道正式可用的中文考试题目，并且只返回 JSON 对象，不要输出 Markdown、解释或代码块。

试卷信息：
- 试卷标题：{paper.paper_title}
- 学科：{paper.meta.get("subject")}
- 学段：{paper.meta.get("school_stage")}
- 年级：{paper.meta.get("grade")}
- 考试类型：{paper.meta.get("exam_type")}
- 语言：{paper.meta.get("language", "zh-CN")}

大题信息：
- 大题名称：{section.section_name}
- 大题说明：{section.instructions or "无"}

当前题位要求：
- 题目 ID：{question.question_id}
- 题型：{question_type_label}
- 难度：{difficulty_label}
- 分值：{question.score if question.score is not None else "未指定"}
- 知识点：{", ".join(question.knowledge_points) or "未指定"}
- 约束：{", ".join(question.constraints) or "无"}
 {f"- 选项数量：{contract['option_count']}" if contract['option_count'] else ""}

上一版题目：
- 题干：{question.stem}
- 参考答案：{question.reference_answer if question.reference_answer is not None else "无"}
- 参考解析：{question.explanation or "无"}

当前持续生效的整卷指导：
{json.dumps(paper_level_guidance, ensure_ascii=False)}

最近几轮教师反馈摘要：
{json.dumps(
    [
        {
            "summary": item.summary,
            "strategy": item.strategy,
            "guidance": item.paper_level_guidance,
        }
        for item in recent_feedback_memory
    ],
    ensure_ascii=False,
)}

教师要求：
- 重生成原因：{review_comment or "老师要求换一道新题，请避免沿用上一版题干与表述。"}

输出要求：
1. 必须输出严格合法的 JSON 对象。
2. 新题必须和上一版题目有明显区别，不能只是改几个字。
 3. 如果存在整卷级指导，必须优先满足整卷级指导，再满足本题要求。
 4. {contract["stem_instruction"]}
 5. {contract["option_instruction"]}
 6. {contract["answer_instruction"]}
 7. {contract["explanation_instruction"]}
 8. `knowledge_points` 应尽量与当前题位要求一致。
 9. 不要输出超纲、模糊、答案不唯一的题目。
 10. {contract["extra_rule"]}

JSON 结构示例：
{json.dumps(contract["schema_hint"], ensure_ascii=False)}
""".strip()

    return [
        {
            "role": "system",
            "content": (
                "你是一名严谨的中文命题老师。你的任务是根据审核意见重生成结构化题目 JSON。"
                "你只能输出合法 JSON 对象，不能输出任何额外解释。"
            ),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _build_question_output_contract(
    *,
    question_type: str,
    knowledge_points: list[str],
    include_answers: bool,
    include_explanations: bool,
) -> dict[str, Any]:
    """按题型生成更窄的输出契约，减少模型自由发挥空间。"""

    kps = knowledge_points or ["核心知识点"]
    option_count = CHOICE_OPTION_COUNT.get(question_type, 0)
    compact_mode = _requires_compact_solution_mode(question_type)

    if question_type == QuestionType.SingleChoice.value:
        schema_hint = {
            "stem": f"以下关于{kps[0]}的说法，正确的是：",
            "options": [
                {"label": "A", "content": "干扰项一", "is_correct": False},
                {"label": "B", "content": "正确项", "is_correct": True},
                {"label": "C", "content": "干扰项二", "is_correct": False},
                {"label": "D", "content": "干扰项三", "is_correct": False},
            ],
            "reference_answer": "B" if include_answers else None,
            "explanation": "说明正确选项依据，并点出其余选项错误点。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干必须聚焦 1 个清晰判断点，不要扩展成长题。"
        extra_rule = "选择题不要输出计算过程或长段解析。"
        max_tokens = 850
    elif question_type == QuestionType.MultipleChoice.value:
        schema_hint = {
            "stem": f"下列关于{kps[0]}的说法，正确的有：",
            "options": [
                {"label": "A", "content": "正确项一", "is_correct": True},
                {"label": "B", "content": "正确项二", "is_correct": True},
                {"label": "C", "content": "干扰项一", "is_correct": False},
                {"label": "D", "content": "干扰项二", "is_correct": False},
            ],
            "reference_answer": ["A", "B"] if include_answers else None,
            "explanation": "简述多选依据，并指出错误项。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干必须聚焦 1 个清晰判断点，不要扩展成长题。"
        extra_rule = "多选题正确项数量控制在 2 个以内。"
        max_tokens = 900
    elif question_type == QuestionType.TrueFalse.value:
        schema_hint = {
            "stem": f"判断：{kps[0]} 的表述是否正确？",
            "options": [
                {"label": "A", "content": "正确", "is_correct": True},
                {"label": "B", "content": "错误", "is_correct": False},
            ],
            "reference_answer": "正确" if include_answers else None,
            "explanation": "一句话说明判断依据。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干只保留 1 个完整判断句。"
        extra_rule = "不要把判断题扩写成分析题。"
        max_tokens = 700
    elif question_type == QuestionType.ShortAnswer.value:
        schema_hint = {
            "stem": f"请简要说明{kps[0]}的核心内容。",
            "options": [],
            "reference_answer": ["要点1", "要点2", "要点3"] if include_answers else None,
            "explanation": "评分时关注定义、关键条件和结论。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干只设置 1 个主任务，不要扩写成多问综合题。"
        extra_rule = "采用短答案模式：reference_answer 最多 3 条要点，每条尽量不超过 25 字。"
        max_tokens = 950
    elif question_type == QuestionType.Calculation.value:
        schema_hint = {
            "stem": f"请计算并求出与{kps[0]}相关的结果。",
            "options": [],
            "reference_answer": ["关键步骤1", "关键步骤2", "最终结果"] if include_answers else None,
            "explanation": "只保留评分关键步骤，不展开完整长解。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干只保留 1 道主计算任务，避免多小问拼接。"
        extra_rule = "采用短答案模式：reference_answer 只保留关键步骤和最终结果，不写长篇完整过程。"
        max_tokens = 1000
    elif question_type == QuestionType.Composite.value:
        schema_hint = {
            "stem": f"请围绕{kps[0]}完成综合作答（最多 2 小问）。",
            "options": [],
            "reference_answer": ["得分点1", "得分点2", "结论"] if include_answers else None,
            "explanation": "点明综合题评分关注点。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干最多 2 个小问，不要扩展成过长的大题。"
        extra_rule = "采用短答案模式：reference_answer 只保留 3 到 4 个得分点，避免完整范文式作答。"
        max_tokens = 1100
    else:
        schema_hint = {
            "stem": f"请围绕{kps[0]}完成作答。",
            "options": [],
            "reference_answer": "答案要点一；答案要点二。" if include_answers else None,
            "explanation": "解析应说明评分关注点和核心知识依据。" if include_explanations else None,
            "knowledge_points": kps,
        }
        stem_instruction = "题干保持单一主题，避免无关扩写。"
        extra_rule = "答案和解析保持简洁，不要生成超长说明。"
        max_tokens = 1100

    option_instruction = (
        f"必须提供 {option_count} 个选项，并使用 is_correct 标记正确项。"
        if option_count
        else "options 必须返回空数组。"
    )
    answer_instruction = (
        "必须填写 reference_answer。"
        if include_answers
        else "reference_answer 返回 null。"
    )
    explanation_instruction = (
        "必须填写 explanation。"
        if include_explanations
        else "explanation 返回 null。"
    )
    if compact_mode and include_explanations:
        explanation_instruction = "explanation 只保留 1 到 2 句评分提示，不要展开长段解析。"

    return {
        "schema_hint": schema_hint,
        "option_count": option_count,
        "stem_instruction": stem_instruction,
        "option_instruction": option_instruction,
        "answer_instruction": answer_instruction,
        "explanation_instruction": explanation_instruction,
        "extra_rule": extra_rule,
        "max_tokens": max_tokens,
        "compact_mode": compact_mode,
    }


def _build_json_repair_messages(
    raw_response: str,
    context_label: str,
    *,
    question_type: str,
    include_answers: bool,
    include_explanations: bool,
) -> list[dict[str, str]]:
    """当首次解析失败时，让模型只做结构修复，不重新发挥写作。"""

    contract = _build_question_output_contract(
        question_type=question_type,
        knowledge_points=["知识点1"],
        include_answers=include_answers,
        include_explanations=include_explanations,
    )

    return [
        {
            "role": "system",
            "content": (
                "你是严格的 JSON 修复器。你的唯一任务是把输入内容整理成一个合法 JSON 对象。"
                "禁止输出 Markdown、解释、前后缀说明，只能输出 JSON。"
                "必须包含字段：stem、options、reference_answer、explanation、knowledge_points。"
                "如果原文是选择题但选项信息不完整，可保留已有语义并最小化补全结构。"
                "如果是简答/计算/综合题，请使用短答案模式，不要展开成长篇完整解答。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"当前题位：{context_label}\n"
                "请把下面这段模型原始输出整理成合法 JSON。\n"
                f"目标结构示例：{json.dumps(contract['schema_hint'], ensure_ascii=False)}\n"
                f"额外要求：{contract['extra_rule']}\n"
                f"原始输出：\n{raw_response}"
            ),
        },
    ]


async def _repair_question_payload_with_llm(
    raw_response: str,
    cfg: Config,
    context_label: str,
    *,
    question_type: str,
    include_answers: bool,
    include_explanations: bool,
) -> dict[str, Any]:
    """当直接解析失败时，用第二次 LLM 调用只做 JSON 修复。"""

    repair_messages = _build_json_repair_messages(
        raw_response,
        context_label,
        question_type=question_type,
        include_answers=include_answers,
        include_explanations=include_explanations,
    )
    repaired_response = await asyncio.wait_for(
        create_chat_completion(
            messages=repair_messages,
            model=cfg.smart_llm_model,
            temperature=0.0,
            max_tokens=min(cfg.smart_token_limit, 1200),
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=_get_exam_llm_kwargs(cfg, cfg.smart_llm_provider),
            reasoning_effort=_get_exam_reasoning_effort(cfg, cfg.smart_llm_provider),
            max_attempts=2,
            retry_delay_cap=2,
        ),
        timeout=60.0,
    )
    _log_raw_response(context_label, "json_repair", repaired_response)
    repaired_payload = _normalize_question_payload(_extract_json_payload(repaired_response))
    if not repaired_payload.get("stem"):
        raise ValueError("LLM repair payload missing stem")
    return repaired_payload


async def _parse_question_payload(
    raw_response: str,
    cfg: Config,
    context_label: str,
    *,
    question_type: str,
    include_answers: bool,
    include_explanations: bool,
) -> dict[str, Any]:
    """先直接解析；失败时再走一次“仅修 JSON”回退。"""

    try:
        payload = _normalize_question_payload(_extract_json_payload(raw_response))
        if not payload.get("stem"):
            raise ValueError("LLM payload missing stem")
        return payload
    except Exception as exc:
        logger.warning(
            "Direct payload parse failed for %s: %s | raw=%s",
            context_label,
            _format_exception_message(exc),
            _preview_text(raw_response),
        )
        try:
            return await _repair_question_payload_with_llm(
                raw_response,
                cfg,
                context_label,
                question_type=question_type,
                include_answers=include_answers,
                include_explanations=include_explanations,
            )
        except Exception as repair_exc:
            raise ValueError(
                f"LLM payload parse and repair both failed for {context_label}: "
                f"{_format_exception_message(exc)}; repair error: {_format_exception_message(repair_exc)}"
            ) from repair_exc


def _build_question_prompt(
    exam_request: ExamPaperRequest,
    section: dict[str, Any],
    slot: dict[str, Any],
) -> list[dict[str, str]]:
    """为单题生成构造 messages。"""

    question_type = slot["question_type"]
    question_type_label = QUESTION_TYPE_LABELS.get(question_type, question_type)
    difficulty = slot.get("difficulty")
    difficulty_label = DIFFICULTY_LABELS.get(difficulty, "常规")
    kps = slot.get("knowledge_points") or ["核心知识点"]
    include_answers = exam_request.generation_policy.include_answers
    include_explanations = exam_request.generation_policy.include_explanations
    score = slot.get("score")
    constraints = slot.get("constraints") or []
    contract = _build_question_output_contract(
        question_type=question_type,
        knowledge_points=kps,
        include_answers=include_answers,
        include_explanations=include_explanations,
    )

    schema_hint = json.dumps(contract["schema_hint"], ensure_ascii=False)
    constraint_text = "；".join(str(item).strip() for item in constraints if str(item).strip()) or "无额外限制"

    return [
        {
            "role": "system",
            "content": (
                "你是一名严谨的中文命题老师。"
                "你只能输出一个严格合法的 JSON 对象，不能输出 Markdown、解释、前后缀。"
                "字段名必须严格使用：stem、options、reference_answer、explanation、knowledge_points。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"请为《{exam_request.paper_title}》生成一道题目。\n"
                f"题位: {slot['slot_id']}\n"
                f"所属大题: {section['section_name']}\n"
                f"题型: {question_type_label}\n"
                f"难度: {difficulty_label}\n"
                f"分值: {score if score is not None else '未指定'}\n"
                f"知识点: {'、'.join(kps)}\n"
                f"额外约束: {constraint_text}\n\n"
                "输出要求：\n"
                "1. 只输出 JSON 对象。\n"
                f"2. {contract['stem_instruction']}\n"
                f"3. {contract['option_instruction']}\n"
                f"4. {contract['answer_instruction']}\n"
                f"5. {contract['explanation_instruction']}\n"
                "6. `knowledge_points` 必须返回数组，并尽量贴合当前题位要求。\n"
                f"7. {contract['extra_rule']}\n"
                "8. 不要输出超纲、题意不清、答案不唯一或模板占位痕迹。\n\n"
                f"输出结构示例：{schema_hint}"
            ),
        },
    ]


def _build_options_from_payload(
    payload: dict[str, Any],
    question_type: str,
    reference_answer: str | list[str] | None,
    fallback_knowledge_point: str,
) -> list[ExamQuestionOption]:
    raw_options = payload.get("options") or []
    normalized_answers = set()

    if isinstance(reference_answer, list):
        normalized_answers = {str(item).strip().upper() for item in reference_answer}
    elif isinstance(reference_answer, str) and len(reference_answer.strip()) <= 4:
        normalized_answers = {part.strip().upper() for part in re.split(r"[,/、\s]+", reference_answer) if part.strip()}

    options: list[ExamQuestionOption] = []
    if isinstance(raw_options, list):
        for index, raw_option in enumerate(raw_options):
            if isinstance(raw_option, str):
                label = chr(ord("A") + index)
                options.append(
                    ExamQuestionOption(
                        label=label,
                        content=_string_or_none(raw_option) or f"{fallback_knowledge_point} 相关选项 {label}",
                        is_correct=label.strip().upper() in normalized_answers,
                    )
                )
                continue

            if not isinstance(raw_option, dict):
                continue

            label = _string_or_none(
                _pick_first_present(raw_option, ["label", "key", "option", "选项", "序号"])
            ) or chr(ord("A") + index)
            content = _string_or_none(
                _pick_first_present(raw_option, ["content", "text", "value", "内容"])
            ) or f"{fallback_knowledge_point} 相关选项 {label}"
            is_correct = _pick_first_present(raw_option, ["is_correct", "correct", "正确", "是否正确"])
            if is_correct is None:
                is_correct = label.strip().upper() in normalized_answers
            options.append(
                ExamQuestionOption(
                    label=label,
                    content=content,
                    is_correct=_normalize_bool(is_correct),
                )
            )

    if options:
        return options

    return _build_preview_options(question_type, fallback_knowledge_point)


async def _generate_question_with_llm(
    exam_request: ExamPaperRequest,
    section: dict[str, Any],
    slot: dict[str, Any],
    cfg: Config,
) -> ExamDraftQuestion:
    """对单个题位执行真实 LLM 生成。"""

    if slot["source_strategy"] == "question_bank_only":
        return _build_template_question(
            exam_request,
            section,
            slot,
            draft_status="pending_regeneration",
            extra_flags=["question_bank_required", "question_bank_not_integrated"],
        )

    fallback_knowledge_point = _pick_primary_knowledge_point(slot)
    messages = _build_question_prompt(exam_request, section, slot)
    context_label = slot["slot_id"]
    include_answers = exam_request.generation_policy.include_answers
    include_explanations = exam_request.generation_policy.include_explanations
    contract = _build_question_output_contract(
        question_type=slot["question_type"],
        knowledge_points=slot.get("knowledge_points") or [fallback_knowledge_point],
        include_answers=include_answers,
        include_explanations=include_explanations,
    )

    try:
        response = await asyncio.wait_for(
            create_chat_completion(
                messages=messages,
                model=cfg.smart_llm_model,
                temperature=0.0,
                max_tokens=min(cfg.smart_token_limit, contract["max_tokens"]),
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=_get_exam_llm_kwargs(cfg, cfg.smart_llm_provider),
                reasoning_effort=_get_exam_reasoning_effort(cfg, cfg.smart_llm_provider),
                max_attempts=3,
                retry_delay_cap=3,
            ),
            timeout=120.0
        )
        if not response or not response.strip():
            raise ValueError("LLM returned empty response")
        _log_raw_response(context_label, "initial_generation", response)
        payload = await _parse_question_payload(
            response,
            cfg,
            context_label,
            question_type=slot["question_type"],
            include_answers=include_answers,
            include_explanations=include_explanations,
        )

        stem = payload.get("stem")

        reference_answer = (
            payload.get("reference_answer")
            if include_answers
            else None
        )
        explanation = (
            payload.get("explanation")
            if include_explanations
            else None
        )
        if contract["compact_mode"]:
            reference_answer = _compact_reference_answer(reference_answer)
            explanation = _trim_compact_text(explanation, max_chars=90)
        knowledge_points = payload.get("knowledge_points") or (slot.get("knowledge_points") or [])
        options = _build_options_from_payload(
            payload,
            slot["question_type"],
            reference_answer,
            fallback_knowledge_point,
        )

        quality_flags = ["ai_generated_preview"]
        if slot["source_strategy"] == "question_bank_first_then_ai":
            quality_flags.append("question_bank_not_integrated")
        if slot.get("score") is None:
            quality_flags.append("missing_score")
        if not knowledge_points:
            quality_flags.append("missing_knowledge_points")

        return ExamDraftQuestion(
            question_id=f"Q-{slot['slot_id']}",
            slot_id=slot["slot_id"],
            order=slot["global_slot_index"],
            section_order=section["section_order"],
            section_name=section["section_name"],
            question_type=slot["question_type"],
            difficulty=slot.get("difficulty"),
            score=slot.get("score"),
            source_strategy=slot["source_strategy"],
            draft_status="generated_preview",
            knowledge_points=knowledge_points,
            stem=stem,
            options=options,
            reference_answer=reference_answer,
            explanation=explanation,
            constraints=slot.get("constraints") or [],
            quality_flags=quality_flags,
            last_regeneration_diff=None,
        )
    except Exception as exc:
        logger.warning(
            "Failed to generate exam question for slot %s: %s",
            slot["slot_id"],
            _format_exception_message(exc),
        )
        return _build_template_question(
            exam_request,
            section,
            slot,
            draft_status="pending_regeneration",
            extra_flags=["llm_generation_failed"],
        )


async def _regenerate_question_with_llm(
    paper: ExamPaperDraft,
    section: ExamDraftSection,
    question: ExamDraftQuestion,
    cfg: Config,
    *,
    review_comment: str | None = None,
) -> ExamDraftQuestion:
    """对已有草案题执行真实的单题重生成。"""

    fallback_knowledge_point = question.knowledge_points[0] if question.knowledge_points else "核心知识点"
    messages = _build_regeneration_prompt(paper, section, question, review_comment)
    context_label = f"{question.slot_id}/regeneration"
    include_answers = bool(paper.generation_policy.get("include_answers", True))
    include_explanations = bool(paper.generation_policy.get("include_explanations", True))
    contract = _build_question_output_contract(
        question_type=question.question_type,
        knowledge_points=question.knowledge_points or [fallback_knowledge_point],
        include_answers=include_answers,
        include_explanations=include_explanations,
    )
    response = await asyncio.wait_for(
        create_chat_completion(
            messages=messages,
            model=cfg.smart_llm_model,
            temperature=0.1,
            max_tokens=min(cfg.smart_token_limit, contract["max_tokens"]),
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=_get_exam_llm_kwargs(cfg, cfg.smart_llm_provider),
            reasoning_effort=_get_exam_reasoning_effort(cfg, cfg.smart_llm_provider),
            max_attempts=3,
            retry_delay_cap=3,
        ),
        timeout=120.0,
    )
    if not response or not response.strip():
        raise ValueError("LLM returned empty regeneration response")
    _log_raw_response(context_label, "regeneration", response)
    payload = await _parse_question_payload(
        response,
        cfg,
        context_label,
        question_type=question.question_type,
        include_answers=include_answers,
        include_explanations=include_explanations,
    )

    stem = payload.get("stem")

    reference_answer = (
        payload.get("reference_answer")
        if include_answers
        else None
    )
    explanation = (
        payload.get("explanation")
        if include_explanations
        else None
    )
    if contract["compact_mode"]:
        reference_answer = _compact_reference_answer(reference_answer)
        explanation = _trim_compact_text(explanation, max_chars=90)
    knowledge_points = payload.get("knowledge_points") or list(question.knowledge_points)
    options = _build_options_from_payload(
        payload,
        question.question_type,
        reference_answer,
        fallback_knowledge_point,
    )

    quality_flags = _dedupe_strings(
        [
            "ai_generated_preview",
            "regenerated_after_review",
            *(
                ["question_bank_not_integrated"]
                if question.source_strategy == "question_bank_first_then_ai"
                else []
            ),
            *_build_quality_flags_from_question(question),
        ]
    )

    return ExamDraftQuestion(
        question_id=question.question_id,
        slot_id=question.slot_id,
        order=question.order,
        section_order=question.section_order,
        section_name=question.section_name,
        question_type=question.question_type,
        difficulty=question.difficulty,
        score=question.score,
        source_strategy=question.source_strategy,
        draft_status="generated_preview",
        review_status="pending_review",
        knowledge_points=knowledge_points,
        stem=stem,
        options=options,
        reference_answer=reference_answer,
        explanation=explanation,
        constraints=list(question.constraints),
        quality_flags=quality_flags,
        quality_issues=[],
        review_comments=list(question.review_comments),
        review_history=list(question.review_history),
        last_regeneration_diff=None,
    )


def _refresh_paper_generation_metadata(
    paper: ExamPaperDraft,
    *,
    extra_note: str | None = None,
) -> ExamPaperDraft:
    """根据当前题目状态回写整卷级生成摘要。"""

    updated_paper = paper.model_copy(deep=True)
    generated_count = 0
    template_count = 0
    pending_regeneration_count = 0

    for section in updated_paper.sections:
        for question in section.questions:
            if question.draft_status == "generated_preview":
                generated_count += 1
            elif question.draft_status == "pending_regeneration":
                pending_regeneration_count += 1
            else:
                template_count += 1

    if generated_count and pending_regeneration_count == 0 and template_count == 0:
        updated_paper.generation_stage = "generated_preview"
    elif generated_count:
        updated_paper.generation_stage = "mixed_preview"
    else:
        updated_paper.generation_stage = "template_preview"

    summary_note = (
        f"{GENERATION_SUMMARY_PREFIX}成功生成 {generated_count} 题，"
        f"模板回退 {template_count} 题，待重生成 {pending_regeneration_count} 题。"
    )
    preserved_notes = [
        note for note in updated_paper.generation_notes if not note.startswith(GENERATION_SUMMARY_PREFIX)
    ]
    updated_paper.generation_notes = [summary_note, *preserved_notes]
    if extra_note:
        updated_paper.generation_notes = _dedupe_strings([extra_note, *updated_paper.generation_notes])
    return updated_paper


async def regenerate_question_in_paper(
    paper: ExamPaperDraft,
    question_id: str,
    *,
    review_comment: str | None = None,
) -> tuple[ExamPaperDraft, list[ExamQualityIssue]]:
    """在已有草案上执行真实的单题重生成。

    返回：
    - 更新后的试卷草案
    - 本次重生成产生的 warnings
    """

    updated_paper = paper.model_copy(deep=True)
    warnings: list[ExamQualityIssue] = []
    target_section_index = -1
    target_question_index = -1

    for section_index, section in enumerate(updated_paper.sections):
        for question_index, question in enumerate(section.questions):
            if question.question_id == question_id:
                target_section_index = section_index
                target_question_index = question_index
                break
        if target_section_index >= 0:
            break

    if target_section_index < 0 or target_question_index < 0:
        raise KeyError(f"question_id={question_id} not found")

    target_section = updated_paper.sections[target_section_index]
    target_question = target_section.questions[target_question_index]

    if target_question.source_strategy == "question_bank_only":
        target_question.review_status = "pending_review"
        target_question.draft_status = "pending_regeneration"
        target_question.quality_flags = _dedupe_strings(
            [
                *target_question.quality_flags,
                "review_requested_regeneration",
                "question_bank_required",
                "question_bank_not_integrated",
            ]
        )
        warnings.append(
            _issue(
                "warning",
                "question_bank_regeneration_unavailable",
                "该题位是 question_bank_only，但题库重抽链路尚未接入，当前仅保留为待重生成状态。",
                f"paper.sections[{target_section_index}].questions[{target_question_index}]",
            )
        )
        refreshed_paper = _refresh_paper_generation_metadata(
            updated_paper,
            extra_note="有题目请求重生成，但因题库链路未接入，暂时无法完成题库重抽。",
        )
        return validate_exam_draft_quality(refreshed_paper), warnings

    cfg = _get_llm_config()
    try:
        regenerated_question = await _regenerate_question_with_llm(
            updated_paper,
            target_section,
            target_question,
            cfg,
            review_comment=review_comment,
        )
        regenerated_question.review_status = "pending_review"
        regenerated_question.review_comments = list(target_question.review_comments)
        regenerated_question.review_history = list(target_question.review_history)
        regenerated_question.last_regeneration_diff = _build_regeneration_diff(
            target_question,
            regenerated_question,
            review_comment=review_comment,
        )
        regenerated_question.quality_flags = _dedupe_strings(
            [
                *regenerated_question.quality_flags,
                *(
                    flag
                    for flag in target_question.quality_flags
                    if flag not in {"review_rejected", "review_requested_regeneration", "regeneration_failed"}
                ),
            ]
        )
        target_section.questions[target_question_index] = regenerated_question

        refreshed_paper = _refresh_paper_generation_metadata(
            updated_paper,
            extra_note=f"题目 {question_id} 已根据审核意见完成重生成。",
        )
        return validate_exam_draft_quality(refreshed_paper), warnings
    except Exception as exc:
        logger.warning(
            "Failed to regenerate exam question %s: %s",
            question_id,
            _format_exception_message(exc),
        )
        target_question.review_status = "pending_review"
        target_question.draft_status = "pending_regeneration"
        target_question.quality_flags = _dedupe_strings(
            [
                *target_question.quality_flags,
                "review_requested_regeneration",
                "regeneration_failed",
            ]
        )
        warnings.append(
            _issue(
                "warning",
                "regeneration_failed",
                f"题目重生成失败，已保留原草案并标记为待重生成：{_format_exception_message(exc)}",
                f"paper.sections[{target_section_index}].questions[{target_question_index}]",
            )
        )
        refreshed_paper = _refresh_paper_generation_metadata(
            updated_paper,
            extra_note=f"题目 {question_id} 发起过重生成，但本次 LLM 重生成失败。",
        )
        return validate_exam_draft_quality(refreshed_paper), warnings


async def generate_exam_preview_paper(
    exam_request: ExamPaperRequest,
    validation_result: dict[str, Any],
    progress_callback=None,
) -> ExamPaperDraft:
    """根据组卷请求构造题目级试卷草案。

    行为说明：
    - AI 可参与的题位优先调用 LLM 生成真实题目草案
    - 纯题库题位目前仍回退为模板占位，因为题库尚未接入
    - 单题失败不影响整张卷子，只把失败题位回退为模板
    """

    await _emit_progress(
        progress_callback,
        stage="building_blueprint",
        message="正在构建试卷蓝图。",
    )
    preview = build_exam_paper_preview(exam_request, validation_result)
    cfg = _get_llm_config()
    max_concurrency = max(1, int(os.environ.get("AI_EXAM_DRAFT_MAX_CONCURRENCY", "1")))
    semaphore = asyncio.Semaphore(max_concurrency)
    sections: list[ExamDraftSection] = []
    progress_lock = asyncio.Lock()

    generated_count = 0
    template_count = 0
    pending_regeneration_count = 0
    progress_state = {
        "total_slots": 0,
        "completed_slots": 0,
        "generated_slots": 0,
        "template_slots": 0,
        "pending_regeneration_slots": 0,
    }

    async def generate_with_limit(section: dict[str, Any], slot: dict[str, Any], idx: int, total: int) -> ExamDraftQuestion:
        async with semaphore:
            logger.info(f"正在生成题目 {idx}/{total} ({slot['slot_id']})...")
            await _emit_progress(
                progress_callback,
                stage="question_started",
                message=f"正在生成题目 {idx}/{total}（{slot['slot_id']}）。",
                metadata={
                    "slot_id": slot["slot_id"],
                    "section_name": section["section_name"],
                    "question_type": slot["question_type"],
                    "index": idx,
                    "total": total,
                },
                progress={**progress_state},
            )
            result = await _generate_question_with_llm(exam_request, section, slot, cfg)
            logger.info(f"题目 {idx}/{total} ({slot['slot_id']}) 生成完成，状态: {result.draft_status}")
            async with progress_lock:
                progress_state["completed_slots"] += 1
                if result.draft_status == "generated_preview":
                    progress_state["generated_slots"] += 1
                elif result.draft_status == "pending_regeneration":
                    progress_state["pending_regeneration_slots"] += 1
                else:
                    progress_state["template_slots"] += 1
                await _emit_progress(
                    progress_callback,
                    stage="question_completed",
                    message=f"题目 {idx}/{total}（{slot['slot_id']}）生成完成，状态：{result.draft_status}。",
                    metadata={
                        "slot_id": slot["slot_id"],
                        "section_name": section["section_name"],
                        "question_type": slot["question_type"],
                        "draft_status": result.draft_status,
                        "index": idx,
                        "total": total,
                    },
                    progress={**progress_state},
                )
            return result

    total_slots = sum(len(section["question_slots"]) for section in preview["sections"])
    progress_state["total_slots"] = total_slots
    logger.info("试卷草案生成启动：总题位=%s，并发数=%s", total_slots, max_concurrency)
    await _emit_progress(
        progress_callback,
        stage="draft_generation_started",
        message=f"试卷草案生成启动：总题位={total_slots}，并发数={max_concurrency}。",
        metadata={"total_slots": total_slots, "max_concurrency": max_concurrency},
        progress={**progress_state},
    )

    flat_generation_jobs: list[tuple[int, dict[str, Any], dict[str, Any], int]] = []
    for section_index, section in enumerate(preview["sections"]):
        for slot in section["question_slots"]:
            flat_generation_jobs.append(
                (section_index, section, slot, len(flat_generation_jobs) + 1)
            )

    generation_tasks = [
        generate_with_limit(section, slot, job_index, total_slots)
        for _, section, slot, job_index in flat_generation_jobs
    ]
    generated_questions = await asyncio.gather(*generation_tasks)

    questions_by_section: dict[int, list[ExamDraftQuestion]] = {
        section_index: []
        for section_index in range(len(preview["sections"]))
    }

    for (section_index, _, _, _), question in zip(flat_generation_jobs, generated_questions):
        questions_by_section[section_index].append(question)
        if question.draft_status == "generated_preview":
            generated_count += 1
        elif question.draft_status == "pending_regeneration":
            pending_regeneration_count += 1
        else:
            template_count += 1

    for section_index, section in enumerate(preview["sections"]):
        questions = questions_by_section[section_index]
        sections.append(
            ExamDraftSection(
                section_name=section["section_name"],
                section_order=section["section_order"],
                instructions=section.get("instructions"),
                requested_section_score=section.get("requested_section_score"),
                computed_section_score=section.get("computed_section_score"),
                question_count=len(questions),
                questions=questions,
            )
        )

    if generated_count and pending_regeneration_count == 0 and template_count == 0:
        generation_stage = "generated_preview"
    elif generated_count:
        generation_stage = "mixed_preview"
    else:
        generation_stage = "template_preview"

    paper = ExamPaperDraft(
        paper_id=_build_paper_id(exam_request),
        paper_title=preview["paper_title"],
        generation_stage=generation_stage,
        meta=preview["meta"],
        totals=preview["totals"],
        generation_policy=preview["generation_policy"],
        source_scope=preview["source_scope"],
        request_snapshot=exam_request.model_dump(mode="json"),
        knowledge_points=preview["knowledge_points"],
        sections=sections,
        generation_notes=[
            (
                f"本次草案生成统计：成功生成 {generated_count} 题，"
                f"模板回退 {template_count} 题，待重生成 {pending_regeneration_count} 题。"
            ),
            (
                "当前阶段已接入真实 LLM 题目生成，但题库抽题尚未接入；"
                "question_bank_only 题位会先保留为待补全状态。"
            ),
            *preview["generation_notes"],
        ],
        review_checklist=preview["review_checklist"],
        warnings=preview["warnings"],
    )
    validated_paper = validate_exam_draft_quality(paper)
    await _emit_progress(
        progress_callback,
        stage="draft_generation_completed",
        level="success",
        message=(
            f"试卷草案生成完成：成功生成 {generated_count} 题，"
            f"模板回退 {template_count} 题，待重生成 {pending_regeneration_count} 题。"
        ),
        metadata={
            "generation_stage": validated_paper.generation_stage,
            "paper_id": validated_paper.paper_id,
        },
        progress={**progress_state},
    )
    return validated_paper
