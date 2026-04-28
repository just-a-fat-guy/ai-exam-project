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
    option_count = CHOICE_OPTION_COUNT.get(question.question_type)
    include_answers = bool(paper.generation_policy.get("include_answers", True))
    include_explanations = bool(paper.generation_policy.get("include_explanations", True))

    json_schema_hint = {
        "stem": "新的题干文本",
        "options": [
            {
                "label": "A",
                "content": "选项内容",
                "is_correct": True,
            }
        ],
        "reference_answer": "参考答案，选择题可用 'A' 或 ['A','C']",
        "explanation": "参考解析",
        "knowledge_points": ["知识点1", "知识点2"],
    }

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
{f"- 选项数量：{option_count}" if option_count else ""}

上一版题目：
- 题干：{question.stem}
- 参考答案：{question.reference_answer if question.reference_answer is not None else "无"}
- 参考解析：{question.explanation or "无"}

教师要求：
- 重生成原因：{review_comment or "老师要求换一道新题，请避免沿用上一版题干与表述。"}

输出要求：
1. 必须输出严格合法的 JSON 对象。
2. 新题必须和上一版题目有明显区别，不能只是改几个字。
3. `stem` 必须完整可读，不能保留模板痕迹。
4. 选择题必须输出 `options`，并用 `is_correct` 标注正确选项。
5. 非选择题 `options` 返回空数组。
6. {"必须输出 `reference_answer`。" if include_answers else "`reference_answer` 允许为 null。"}
7. {"必须输出 `explanation`。" if include_explanations else "`explanation` 允许为 null。"}
8. `knowledge_points` 应尽量与当前题位要求一致。
9. 不要输出超纲、模糊、答案不唯一的题目。

JSON 结构示例：
{json.dumps(json_schema_hint, ensure_ascii=False)}
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


def _build_json_repair_messages(raw_response: str, context_label: str) -> list[dict[str, str]]:
    """当首次解析失败时，让模型只做结构修复，不重新发挥写作。"""

    example = {
        "stem": "题干",
        "options": [
            {"label": "A", "content": "选项内容", "is_correct": False},
            {"label": "B", "content": "选项内容", "is_correct": True},
        ],
        "reference_answer": "B",
        "explanation": "答案解析",
        "knowledge_points": ["知识点1"],
    }

    return [
        {
            "role": "system",
            "content": (
                "你是严格的 JSON 修复器。你的唯一任务是把输入内容整理成一个合法 JSON 对象。"
                "禁止输出 Markdown、解释、前后缀说明，只能输出 JSON。"
                "必须包含字段：stem、options、reference_answer、explanation、knowledge_points。"
                "如果原文是选择题但选项信息不完整，可保留已有语义并最小化补全结构。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"当前题位：{context_label}\n"
                "请把下面这段模型原始输出整理成合法 JSON。\n"
                f"目标结构示例：{json.dumps(example, ensure_ascii=False)}\n"
                f"原始输出：\n{raw_response}"
            ),
        },
    ]


async def _repair_question_payload_with_llm(
    raw_response: str,
    cfg: Config,
    context_label: str,
) -> dict[str, Any]:
    """当直接解析失败时，用第二次 LLM 调用只做 JSON 修复。"""

    repair_messages = _build_json_repair_messages(raw_response, context_label)
    repaired_response = await asyncio.wait_for(
        create_chat_completion(
            messages=repair_messages,
            model=cfg.smart_llm_model,
            temperature=0.0,
            max_tokens=min(cfg.smart_token_limit, 1200),
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            reasoning_effort=cfg.reasoning_effort,
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
            exc,
            _preview_text(raw_response),
        )
        try:
            return await _repair_question_payload_with_llm(raw_response, cfg, context_label)
        except Exception as repair_exc:
            raise ValueError(
                f"LLM payload parse and repair both failed for {context_label}: "
                f"{exc}; repair error: {repair_exc}"
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
    option_count = CHOICE_OPTION_COUNT.get(question_type, 0)

    if question_type == QuestionType.SingleChoice.value:
        example_payload: dict[str, Any] = {
            "stem": f"以下关于{kps[0]}的说法，正确的是：",
            "options": [
                {"label": "A", "content": "干扰项一", "is_correct": False},
                {"label": "B", "content": "正确项", "is_correct": True},
                {"label": "C", "content": "干扰项二", "is_correct": False},
                {"label": "D", "content": "干扰项三", "is_correct": False},
            ],
            "reference_answer": "B" if include_answers else None,
            "explanation": "先点明正确依据，再说明其他选项为什么错。" if include_explanations else None,
            "knowledge_points": kps,
        }
    elif question_type == QuestionType.MultipleChoice.value:
        example_payload = {
            "stem": f"下列关于{kps[0]}的说法，正确的有：",
            "options": [
                {"label": "A", "content": "正确项一", "is_correct": True},
                {"label": "B", "content": "正确项二", "is_correct": True},
                {"label": "C", "content": "干扰项一", "is_correct": False},
                {"label": "D", "content": "干扰项二", "is_correct": False},
            ],
            "reference_answer": ["A", "B"] if include_answers else None,
            "explanation": "说明 A/B 的依据，并指出干扰项错误点。" if include_explanations else None,
            "knowledge_points": kps,
        }
    elif question_type == QuestionType.TrueFalse.value:
        example_payload = {
            "stem": f"判断：{kps[0]} 的表述是否正确？",
            "options": [
                {"label": "A", "content": "正确", "is_correct": True},
                {"label": "B", "content": "错误", "is_correct": False},
            ],
            "reference_answer": "正确" if include_answers else None,
            "explanation": "简要说明判断依据。" if include_explanations else None,
            "knowledge_points": kps,
        }
    else:
        example_payload = {
            "stem": f"请围绕{kps[0]}完成作答。",
            "options": [],
            "reference_answer": "答案要点一；答案要点二。" if include_answers else None,
            "explanation": "解析应说明评分关注点和核心知识依据。" if include_explanations else None,
            "knowledge_points": kps,
        }

    schema_hint = json.dumps(example_payload, ensure_ascii=False)
    constraint_text = "；".join(str(item).strip() for item in constraints if str(item).strip()) or "无额外限制"
    option_instruction = (
        f"必须提供 {option_count} 个选项，并使用 is_correct 标记正确项。"
        if option_count
        else "options 必须返回空数组。"
    )
    answer_instruction = "必须填写 reference_answer。" if include_answers else "reference_answer 返回 null。"
    explanation_instruction = "必须填写 explanation。" if include_explanations else "explanation 返回 null。"

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
                "2. `stem` 必须完整、自然、可直接给学生作答。\n"
                f"3. {option_instruction}\n"
                f"4. {answer_instruction}\n"
                f"5. {explanation_instruction}\n"
                "6. `knowledge_points` 必须返回数组，并尽量贴合当前题位要求。\n"
                "7. 不要输出超纲、题意不清、答案不唯一或模板占位痕迹。\n\n"
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

    try:
        response = await asyncio.wait_for(
            create_chat_completion(
                messages=messages,
                model=cfg.smart_llm_model,
                temperature=0.0,
                max_tokens=min(cfg.smart_token_limit, 1600),
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                reasoning_effort=cfg.reasoning_effort,
            ),
            timeout=120.0
        )
        if not response or not response.strip():
            raise ValueError("LLM returned empty response")
        _log_raw_response(context_label, "initial_generation", response)
        payload = await _parse_question_payload(response, cfg, context_label)

        stem = payload.get("stem")

        reference_answer = (
            payload.get("reference_answer")
            if exam_request.generation_policy.include_answers
            else None
        )
        explanation = (
            payload.get("explanation")
            if exam_request.generation_policy.include_explanations
            else None
        )
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
            exc,
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
    response = await asyncio.wait_for(
        create_chat_completion(
            messages=messages,
            model=cfg.smart_llm_model,
            temperature=0.1,
            max_tokens=min(cfg.smart_token_limit, 1600),
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            reasoning_effort=cfg.reasoning_effort,
        ),
        timeout=120.0,
    )
    if not response or not response.strip():
        raise ValueError("LLM returned empty regeneration response")
    _log_raw_response(context_label, "regeneration", response)
    payload = await _parse_question_payload(response, cfg, context_label)

    stem = payload.get("stem")

    include_answers = bool(paper.generation_policy.get("include_answers", True))
    include_explanations = bool(paper.generation_policy.get("include_explanations", True))
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
        logger.warning("Failed to regenerate exam question %s: %s", question_id, exc)
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
                f"题目重生成失败，已保留原草案并标记为待重生成：{exc}",
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
) -> ExamPaperDraft:
    """根据组卷请求构造题目级试卷草案。

    行为说明：
    - AI 可参与的题位优先调用 LLM 生成真实题目草案
    - 纯题库题位目前仍回退为模板占位，因为题库尚未接入
    - 单题失败不影响整张卷子，只把失败题位回退为模板
    """

    preview = build_exam_paper_preview(exam_request, validation_result)
    cfg = _get_llm_config()
    max_concurrency = max(1, int(os.environ.get("AI_EXAM_DRAFT_MAX_CONCURRENCY", "1")))
    semaphore = asyncio.Semaphore(max_concurrency)
    sections: list[ExamDraftSection] = []

    generated_count = 0
    template_count = 0
    pending_regeneration_count = 0

    async def generate_with_limit(section: dict[str, Any], slot: dict[str, Any], idx: int, total: int) -> ExamDraftQuestion:
        async with semaphore:
            logger.info(f"正在生成题目 {idx}/{total} ({slot['slot_id']})...")
            result = await _generate_question_with_llm(exam_request, section, slot, cfg)
            logger.info(f"题目 {idx}/{total} ({slot['slot_id']}) 生成完成，状态: {result.draft_status}")
            return result

    total_slots = sum(len(s["question_slots"]) for s in preview["sections"])
    current_idx = 0

    for section in preview["sections"]:
        section_tasks = []
        for slot in section["question_slots"]:
            current_idx += 1
            section_tasks.append(generate_with_limit(section, slot, current_idx, total_slots))
        questions = await asyncio.gather(*section_tasks)

        for question in questions:
            if question.draft_status == "generated_preview":
                generated_count += 1
            elif question.draft_status == "pending_regeneration":
                pending_regeneration_count += 1
            else:
                template_count += 1

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
    return validate_exam_draft_quality(paper)
