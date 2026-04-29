"""AI 组卷 agent 服务。

这一层处理两类更接近 agent 的决策：

1. 模糊教师需求 -> LLM 规划标准组卷请求
2. 教师整卷反馈 -> LLM 决定哪些题需要通过 / 驳回 / 重生成

和前面的规则解析不同，这里让 LLM 参与“规划”和“决策”，
而不是只参与最后一道题的文本生成。
"""

from __future__ import annotations

import copy
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from gpt_researcher.config.config import Config
from gpt_researcher.utils.llm import create_chat_completion

from schemas import (
    ExamNaturalLanguageParseResult,
    ExamPaperDraft,
    ExamNaturalLanguageRequest,
    ExamPaperRequest,
    ExamPaperReviewRequest,
    ExamQuestionReviewAction,
    ExamQuestionReviewRecord,
    ExamQualityIssue,
    ExamTeacherFeedbackMemoryRecord,
    ExamTeacherFeedbackPlannedAction,
    ExamTeacherFeedbackRequest,
    ExamTeacherFeedbackResult,
    PaperSectionRequirement,
)

from .exam_draft import _extract_json_payload, _preview_text, regenerate_question_in_paper
from .exam_intake import parse_natural_exam_request
from .exam_review import apply_exam_review_actions
from .exam_quality import validate_exam_draft_quality
from .exam_validation import validate_exam_paper_request_model
from .exam_draft import generate_exam_preview_paper


logger = logging.getLogger(__name__)


VALID_QUESTION_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "essay",
    "calculation",
    "case_analysis",
    "reading_comprehension",
    "cloze",
    "translation",
    "practical",
    "composite",
}

QUESTION_TYPE_ALIASES = {
    "single": "single_choice",
    "choice": "single_choice",
    "objective": "single_choice",
    "multiple": "multiple_choice",
    "multiple_choices": "multiple_choice",
    "judge": "true_false",
    "judgement": "true_false",
    "true_or_false": "true_false",
    "blank": "fill_blank",
    "fill": "fill_blank",
    "subjective": "short_answer",
    "qa": "short_answer",
    "calculate": "calculation",
    "application": "practical",
    "practice": "practical",
    "reading": "reading_comprehension",
    "reading_understanding": "reading_comprehension",
    "composition": "essay",
    "comprehensive": "composite",
}


def _issue(level: str, code: str, message: str, path: str) -> ExamQualityIssue:
    return ExamQualityIssue(level=level, code=code, message=message, path=path)


def _get_llm_config() -> Config:
    config_path = os.environ.get("CONFIG_PATH")
    return Config(config_path if config_path and config_path != "default" else None)


def _parse_exam_thinking_payload() -> dict[str, Any] | None:
    """把环境变量里的 thinking 配置转成兼容 ARK 的对象结构。

    支持两种写法：
    1. `AI_EXAM_THINKING=disabled`
       -> {"type": "disabled"}
    2. `AI_EXAM_THINKING={"type":"disabled"}`
       -> 直接按 JSON 对象使用
    """

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
    """为考试链路构造 provider 初始化参数。

    对 OpenAI-compatible 网关，`thinking` 不能作为顶层调用参数直接传给
    openai-python 的 `chat.completions.create()`，否则会报
    `unexpected keyword argument 'thinking'`。
    这里统一塞进 `extra_body`，让兼容网关在请求体里接收它。
    """

    llm_kwargs = copy.deepcopy(cfg.llm_kwargs or {})
    thinking_payload = _parse_exam_thinking_payload()
    if llm_provider == "openai" and thinking_payload:
        extra_body = llm_kwargs.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body["thinking"] = thinking_payload
        llm_kwargs["extra_body"] = extra_body
    return llm_kwargs or None


def _get_exam_reasoning_effort(cfg: Config, llm_provider: str) -> str | None:
    """考试链路专用的 reasoning_effort 解析。

    如果已经显式传了 `thinking=disabled`，则不再继续传 reasoning_effort，
    避免同一请求里出现两套可能互相冲突的“思考控制”参数。
    """

    llm_kwargs = _get_exam_llm_kwargs(cfg, llm_provider) or {}
    extra_body = llm_kwargs.get("extra_body")
    thinking_config = extra_body.get("thinking") if isinstance(extra_body, dict) else None
    if isinstance(thinking_config, dict) and thinking_config.get("type") == "disabled":
        return None
    return getattr(cfg, "reasoning_effort", None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)
    return ordered


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_top_level_knowledge_points(raw_points: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_points, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_points:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or item.get("knowledge_point") or "").strip()
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "required": bool(item.get("required", True)),
                    "weight": item.get("weight"),
                    "target_question_count": item.get("target_question_count"),
                    "notes": item.get("notes"),
                }
            )
            continue
        name = str(item).strip()
        if name:
            normalized.append({"name": name, "required": True})
    return normalized


def _infer_subjective_question_type(section_name: str, requirement: dict[str, Any]) -> str:
    section_text = f"{section_name} {requirement.get('instructions') or ''}"
    if any(keyword in section_text for keyword in ["计算", "方程", "运算"]):
        return "calculation"
    if any(keyword in section_text for keyword in ["应用", "实践", "操作"]):
        return "practical"
    if any(keyword in section_text for keyword in ["综合", "压轴", "探究"]):
        return "composite"
    if any(keyword in section_text for keyword in ["作文", "写作"]):
        return "essay"
    if any(keyword in section_text for keyword in ["阅读", "文段"]):
        return "reading_comprehension"
    return "short_answer"


def _normalize_question_type_value(raw_type: Any, *, section_name: str, requirement: dict[str, Any]) -> str:
    candidate = str(raw_type or "").strip().lower()
    if not candidate:
        return _infer_subjective_question_type(section_name, requirement)
    if candidate in VALID_QUESTION_TYPES:
        return candidate
    aliased = QUESTION_TYPE_ALIASES.get(candidate)
    if aliased == "short_answer" and candidate == "subjective":
        return _infer_subjective_question_type(section_name, requirement)
    return aliased or candidate


def _normalize_section_requirements_payload(raw_sections: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_sections, list):
        return []
    normalized_sections: list[dict[str, Any]] = []
    for section in raw_sections:
        if not isinstance(section, dict):
            continue
        section_copy = copy.deepcopy(section)
        section_name = str(section_copy.get("section_name") or "").strip()
        raw_requirements = section_copy.get("question_requirements")
        if isinstance(raw_requirements, list):
            normalized_requirements: list[dict[str, Any]] = []
            for requirement in raw_requirements:
                if not isinstance(requirement, dict):
                    continue
                requirement_copy = copy.deepcopy(requirement)
                requirement_copy["question_type"] = _normalize_question_type_value(
                    requirement_copy.get("question_type"),
                    section_name=section_name,
                    requirement=requirement_copy,
                )
                raw_requirement_points = requirement_copy.get("knowledge_points")
                if isinstance(raw_requirement_points, list):
                    normalized_requirement_points: list[str] = []
                    for point in raw_requirement_points:
                        if isinstance(point, dict):
                            point_name = str(
                                point.get("name")
                                or point.get("title")
                                or point.get("knowledge_point")
                                or ""
                            ).strip()
                            if point_name:
                                normalized_requirement_points.append(point_name)
                        else:
                            point_name = str(point).strip()
                            if point_name:
                                normalized_requirement_points.append(point_name)
                    requirement_copy["knowledge_points"] = normalized_requirement_points
                else:
                    requirement_copy["knowledge_points"] = []
                normalized_requirements.append(requirement_copy)
            section_copy["question_requirements"] = normalized_requirements
        normalized_sections.append(section_copy)
    return normalized_sections


def _get_exam_planning_model(cfg: Config) -> tuple[str, str]:
    if cfg.strategic_llm_provider and cfg.strategic_llm_model:
        return cfg.strategic_llm_provider, cfg.strategic_llm_model
    return cfg.smart_llm_provider, cfg.smart_llm_model


def _build_seed_exam_request(
    payload: ExamNaturalLanguageRequest,
) -> tuple[ExamNaturalLanguageParseResult, dict[str, Any] | None]:
    rule_result = parse_natural_exam_request(payload)
    seed_request = copy.deepcopy(rule_result.exam_request) if rule_result.valid and rule_result.exam_request else None
    return rule_result, seed_request


def _normalize_planner_payload(
    seed_request: dict[str, Any] | None,
    llm_payload: dict[str, Any],
    raw_request: ExamNaturalLanguageRequest,
) -> dict[str, Any]:
    candidate_request = llm_payload.get("exam_request") if "exam_request" in llm_payload else llm_payload

    if not isinstance(candidate_request, dict):
        raise ValueError("LLM 输出缺少 exam_request 对象")

    merged = _deep_merge(seed_request or {}, candidate_request)

    generation_policy = merged.setdefault("generation_policy", {})
    generation_policy.setdefault("mode", raw_request.generation_mode.value)
    generation_policy.setdefault("allow_ai_generate_missing", True)
    generation_policy.setdefault("include_answers", raw_request.include_answers)
    generation_policy.setdefault("include_explanations", raw_request.include_explanations)

    review_requirement = merged.setdefault("review_requirement", {})
    review_requirement.setdefault("enabled", True)
    review_requirement.setdefault("require_answer_review", raw_request.include_answers)
    review_requirement.setdefault("require_explanation_review", raw_request.include_explanations)
    review_requirement.setdefault("require_knowledge_point_review", False)

    merged.setdefault("output_formats", raw_request.output_formats)
    merged.setdefault("source_scope", {})
    merged["knowledge_points"] = _normalize_top_level_knowledge_points(merged.get("knowledge_points"))
    merged["sections"] = _normalize_section_requirements_payload(merged.get("sections"))
    merged.setdefault("metadata", {})
    merged["metadata"]["planner_mode"] = "llm"
    merged["metadata"]["raw_user_request"] = raw_request.user_request
    return merged


def _build_planner_structure_hint() -> dict[str, Any]:
    return {
        "task_summary": "一句中文概括",
        "assumptions": ["仅保留必要假设"],
        "exam_request": {
            "paper_title": "小学数学六年级下册期末考试试卷",
            "subject": "math",
            "school_stage": "primary",
            "grade": "grade_6",
            "exam_type": "final",
            "term": "spring",
            "language": "zh-CN",
            "duration_minutes": 40,
            "total_score": 100,
            "target_question_count": 4,
            "knowledge_points": [
                {"name": "负数的认识", "required": True},
                {"name": "比例", "required": True},
            ],
            "sections": [
                {
                    "section_name": "基础题",
                    "section_order": 1,
                    "section_score": 50,
                    "instructions": "考查基础概念和基本计算。",
                    "question_requirements": [
                        {
                            "question_type": "single_choice",
                            "question_count": 2,
                            "knowledge_points": ["负数的认识", "百分数（二）"],
                            "allow_ai_generation": True,
                        }
                    ],
                }
            ],
        },
    }


def _summarize_section_knowledge_point_shapes(sections: Any) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        return []
    summary: list[dict[str, Any]] = []
    for section in sections[:4]:
        if not isinstance(section, dict):
            continue
        for requirement in (section.get("question_requirements") or [])[:4]:
            if not isinstance(requirement, dict):
                continue
            raw_points = requirement.get("knowledge_points")
            point_types: list[str] = []
            if isinstance(raw_points, list):
                point_types = [type(point).__name__ for point in raw_points[:3]]
            summary.append(
                {
                    "section_name": section.get("section_name"),
                    "question_type": requirement.get("question_type"),
                    "knowledge_point_types": point_types,
                    "knowledge_point_preview": raw_points[:3] if isinstance(raw_points, list) else raw_points,
                }
            )
    return summary


def _log_planner_key_fields(stage: str, payload: dict[str, Any]) -> None:
    logger.info(
        "Exam planner %s | target_question_count=%s | top_level_kp_preview=%s | section_kp_shapes=%s",
        stage,
        payload.get("target_question_count"),
        _preview_text(payload.get("knowledge_points")),
        _preview_text(_summarize_section_knowledge_point_shapes(payload.get("sections"))),
    )


def _extract_assumptions_list(llm_payload: dict[str, Any]) -> list[str]:
    assumptions = llm_payload.get("assumptions")
    if not isinstance(assumptions, list):
        return []
    return [str(item).strip() for item in assumptions if str(item).strip()]


def _finalize_exam_planning_result(
    seed_request: dict[str, Any] | None,
    llm_payload: dict[str, Any],
    raw_request: ExamNaturalLanguageRequest,
    extracted: dict[str, Any],
) -> ExamNaturalLanguageParseResult:
    candidate_request = llm_payload.get("exam_request") if "exam_request" in llm_payload else llm_payload
    if not isinstance(candidate_request, dict):
        raise ValueError("LLM 输出缺少 exam_request 对象")
    _log_planner_key_fields("candidate_before_normalize", candidate_request)
    normalized_request = _normalize_planner_payload(seed_request, llm_payload, raw_request)
    _log_planner_key_fields("candidate_after_normalize", normalized_request)
    exam_request = ExamPaperRequest.model_validate(normalized_request)
    return ExamNaturalLanguageParseResult(
        valid=True,
        task_summary=str(llm_payload.get("task_summary") or exam_request.paper_title),
        assumptions=_extract_assumptions_list(llm_payload),
        extracted=extracted,
        exam_request=exam_request.model_dump(),
        errors=[],
    )


def _build_exam_planning_repair_messages(
    payload: ExamNaturalLanguageRequest,
    rule_result: ExamNaturalLanguageParseResult,
    seed_request: dict[str, Any] | None,
    *,
    previous_response: str,
    failure_reason: str,
) -> list[dict[str, str]]:
    structure_hint = json.dumps(_build_planner_structure_hint(), ensure_ascii=False, indent=2)
    system_prompt = """
你是“AI 组卷规划修复 Agent”。

你的职责不是重新解释需求，而是把上一轮不合格的 JSON 规划修正成严格符合后端 schema 的 JSON。

硬性规则：
1. 只输出一个 JSON 对象。
2. 顶层必须包含 task_summary、assumptions、exam_request。
3. 顶层 exam_request.knowledge_points 必须是对象数组：
   [{"name":"知识点","required":true}]
4. section 内 question_requirements[].knowledge_points 必须是字符串数组：
   ["知识点A","知识点B"]
5. 不能把 section 内的 knowledge_points 写成对象数组。
6. question_type 只能使用系统允许的枚举值，不能输出 subjective、objective 之类别名。
7. 尽量保留上一轮已经正确的业务含义，例如题量、学科、年级、考试类型、分区结构。
""".strip()

    user_prompt = f"""
教师原始需求：
{payload.user_request}

规则兜底种子：
{json.dumps(seed_request, ensure_ascii=False, indent=2)}

上一轮 LLM 原始输出：
{previous_response}

上一轮失败原因：
{failure_reason}

正确输出结构示例：
{structure_hint}

请只输出修正后的最终 JSON，不要附加解释。
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_exam_planning_messages(
    payload: ExamNaturalLanguageRequest,
    rule_result: ExamNaturalLanguageParseResult,
    seed_request: dict[str, Any] | None,
) -> list[dict[str, str]]:
    system_prompt = """
你是“AI 组卷规划 Agent”。

你的职责不是直接出题，而是把教师的模糊组卷需求规划成一个可执行的标准 JSON 请求。

必须遵守：
1. 只输出一个 JSON 对象，不要输出解释文字。
2. JSON 顶层必须包含：
   - task_summary: 字符串
   - assumptions: 字符串数组
   - exam_request: 对象
3. exam_request 必须尽量符合当前系统的标准组卷请求结构。
4. 若教师没有明确说明，默认采用纯 AI 出题：
   generation_policy.mode = "ai_generate_only"
5. review_requirement.enabled 必须为 true。
6. 若 include_answers / include_explanations 已给定，必须在 generation_policy 中保持一致。
7. 对于小学 / 初中常见试卷，合理规划 sections、题型数量、分值和知识点覆盖。
8. 输出必须是中文语境下可用的试卷规划，不要虚构题库字段。
9. 顶层 knowledge_points 必须输出对象数组，格式示例：{{"name":"分数乘除法","required":true}}，不能只输出字符串数组。
10. question_requirements.question_type 只能使用这些枚举值：
single_choice, multiple_choice, true_false, fill_blank, short_answer, essay, calculation, case_analysis, reading_comprehension, cloze, translation, practical, composite。
11. section 内 question_requirements[].knowledge_points 必须是字符串数组，例如 ["比例","圆柱与圆锥"]，绝不能输出成对象数组。
12. 顶层 knowledge_points 和 section 内 knowledge_points 结构不同，不能混用。
""".strip()

    user_prompt = f"""
教师原始需求：
{payload.user_request}

前端给定偏好：
{json.dumps(
    {
        "generation_mode": payload.generation_mode.value,
        "include_answers": payload.include_answers,
        "include_explanations": payload.include_explanations,
        "output_formats": payload.output_formats,
    },
    ensure_ascii=False,
    indent=2,
)}

规则解析得到的初步结果（可作为保守兜底，不是最终答案）：
{json.dumps(
    {
        "valid": rule_result.valid,
        "task_summary": rule_result.task_summary,
        "assumptions": rule_result.assumptions,
        "extracted": rule_result.extracted,
        "seed_exam_request": seed_request,
    },
    ensure_ascii=False,
    indent=2,
)}

请输出最终 JSON。要求：
- 如果教师需求存在模糊偏好，例如“难度一般、应用题适中、阅读不要太难”，你需要主动体现在 sections、题型和 notes_to_generator 中。
- 如果规则种子过于死板，可以调整，但不要偏离教师原始需求。
- assumptions 里只保留真正由你自动推断的内容。
- task_summary 用一句自然中文概括本次组卷目标。
- 请特别注意两层 knowledge_points 的结构不同：
  - 顶层 knowledge_points: 对象数组
  - section 内 question_requirements[].knowledge_points: 字符串数组
- 如果教师明确要求题目总数，例如“生成四道题目即可”，target_question_count 和各大题 question_count 总和必须一致。
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def plan_exam_from_natural_request(
    payload: ExamNaturalLanguageRequest,
) -> ExamNaturalLanguageParseResult:
    """优先通过 LLM 把模糊需求规划成标准组卷请求，失败时退回规则解析。"""

    rule_result, seed_request = _build_seed_exam_request(payload)
    cfg = _get_llm_config()
    llm_provider, llm_model = _get_exam_planning_model(cfg)

    raw_response = ""
    try:
        messages = _build_exam_planning_messages(payload, rule_result, seed_request)
        raw_response = await create_chat_completion(
            messages=messages,
            model=llm_model,
            llm_provider=llm_provider,
            temperature=0.1,
            max_tokens=3500,
            llm_kwargs=_get_exam_llm_kwargs(cfg, llm_provider),
            reasoning_effort=_get_exam_reasoning_effort(cfg, llm_provider),
            max_attempts=2,
            retry_delay_cap=2,
        )
        logger.info("LLM exam planning response: %s", _preview_text(raw_response))
        llm_payload = _extract_json_payload(raw_response)
        return _finalize_exam_planning_result(
            seed_request,
            llm_payload,
            payload,
            rule_result.extracted,
        )
    except (ValueError, ValidationError, RuntimeError) as first_exc:
        logger.warning("Initial LLM exam planning failed, attempting repair: %s", first_exc)
        try:
            repair_messages = _build_exam_planning_repair_messages(
                payload,
                rule_result,
                seed_request,
                previous_response=raw_response,
                failure_reason=str(first_exc),
            )
            repaired_response = await create_chat_completion(
                messages=repair_messages,
                model=llm_model,
                llm_provider=llm_provider,
                temperature=0.0,
                max_tokens=3500,
                llm_kwargs=_get_exam_llm_kwargs(cfg, llm_provider),
                reasoning_effort=_get_exam_reasoning_effort(cfg, llm_provider),
                max_attempts=2,
                retry_delay_cap=2,
            )
            logger.info("LLM exam planning repair response: %s", _preview_text(repaired_response))
            repaired_payload = _extract_json_payload(repaired_response)
            return _finalize_exam_planning_result(
                seed_request,
                repaired_payload,
                payload,
                rule_result.extracted,
            )
        except (ValueError, ValidationError, RuntimeError) as repair_exc:
            logger.warning(
                "LLM exam planning failed after repair, falling back to rule planner: initial=%s | repair=%s",
                first_exc,
                repair_exc,
            )

    fallback_assumptions = list(rule_result.assumptions)
    fallback_assumptions.append("本次组卷规划未成功走通 LLM 决策，已自动退回规则模板兜底。")
    return ExamNaturalLanguageParseResult(
        valid=rule_result.valid,
        task_summary=rule_result.task_summary,
        assumptions=fallback_assumptions,
        extracted=rule_result.extracted,
        exam_request=rule_result.exam_request,
        errors=rule_result.errors,
    )


def _build_question_overview_lines(paper: Any) -> list[str]:
    lines: list[str] = []
    for section in paper.sections:
        for question in section.questions:
            lines.append(
                " | ".join(
                    [
                        f"question_id={question.question_id}",
                        f"section={question.section_name}",
                        f"type={question.question_type}",
                        f"score={question.score}",
                        f"difficulty={question.difficulty}",
                        f"review_status={question.review_status}",
                        f"draft_status={question.draft_status}",
                        f"quality_flags={','.join(question.quality_flags) or 'none'}",
                        f"stem={_preview_text(question.stem, limit=120)}",
                    ]
                )
            )
    return lines


def _build_feedback_history_lines(paper: Any, *, keep_last: int = 5) -> list[str]:
    history = list(getattr(paper, "feedback_history", []) or [])
    selected = history[-keep_last:]
    lines: list[str] = []
    for index, record in enumerate(selected, start=1):
        lines.append(
            " | ".join(
                [
                    f"round={index}",
                    f"reviewer={record.reviewer}",
                    f"strategy={record.strategy}",
                    f"summary={_preview_text(record.summary, limit=120)}",
                    f"feedback={_preview_text(record.teacher_feedback, limit=120)}",
                    f"guidance={'; '.join(record.paper_level_guidance) or 'none'}",
                ]
            )
        )
    return lines


def _merge_teacher_comment(
    action_comment: str | None,
    strategy: str,
    paper_level_guidance: list[str],
) -> str | None:
    guidance_text = "；".join(paper_level_guidance)
    action_text = (action_comment or "").strip()
    parts: list[str] = []
    if strategy == "paper_level_regenerate":
        parts.append("本轮属于整卷二次规划，请确保这道题服从新的全卷策略。")
    elif strategy == "section_level_regenerate":
        parts.append("本轮属于大题级重生成，请确保这道题服从新的大题策略。")
    if guidance_text:
        parts.append(f"全卷指导：{guidance_text}")
    if action_text:
        parts.append(f"本题要求：{action_text}")
    merged = " ".join(part for part in parts if part).strip()
    return merged or None


def _append_feedback_memory_to_paper(
    paper: Any,
    *,
    reviewer: str,
    teacher_feedback: str,
    strategy: str,
    summary: str,
    target_sections: list[str],
    target_question_ids: list[str],
    paper_level_guidance: list[str],
    planned_actions: list[ExamTeacherFeedbackPlannedAction],
) -> Any:
    updated_paper = paper.model_copy(deep=True)
    updated_paper.revision_round = int(getattr(updated_paper, "revision_round", 0) or 0) + 1
    updated_paper.paper_level_guidance = _dedupe_strings(
        [*getattr(updated_paper, "paper_level_guidance", []), *paper_level_guidance]
    )
    updated_paper.feedback_history = [
        *getattr(updated_paper, "feedback_history", []),
        ExamTeacherFeedbackMemoryRecord(
            reviewer=reviewer,
            teacher_feedback=teacher_feedback,
            strategy=strategy,
            summary=summary,
            target_sections=target_sections,
            target_question_ids=target_question_ids,
            paper_level_guidance=paper_level_guidance,
            planned_actions=planned_actions,
            timestamp=_now_iso(),
        ),
    ]
    updated_paper.generation_notes = _dedupe_strings(
        [
            f"第 {updated_paper.revision_round} 轮教师反馈已处理：{summary}",
            *getattr(updated_paper, "generation_notes", []),
        ]
    )
    return updated_paper


def _normalize_feedback_strategy(strategy: str) -> str:
    normalized = str(strategy or "").strip()
    legacy_mapping = {
        "targeted_edit": "question_level_edit",
        "whole_paper_replan": "paper_level_regenerate",
    }
    normalized = legacy_mapping.get(normalized, normalized)
    if normalized not in {
        "no_change",
        "question_level_edit",
        "section_level_regenerate",
        "paper_level_regenerate",
    }:
        return "question_level_edit"
    return normalized


def _build_question_lookup(paper: ExamPaperDraft) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for section in paper.sections:
        for question in section.questions:
            lookup[question.question_id] = question
    return lookup


def _get_existing_section_names(paper: ExamPaperDraft) -> list[str]:
    return [section.section_name for section in paper.sections]


def _normalize_target_sections(paper: ExamPaperDraft, raw_sections: Any) -> list[str]:
    if not isinstance(raw_sections, list):
        return []
    existing = set(_get_existing_section_names(paper))
    ordered: list[str] = []
    for item in raw_sections:
        value = str(item).strip()
        if value and value in existing and value not in ordered:
            ordered.append(value)
    return ordered


def _normalize_target_question_ids(paper: ExamPaperDraft, raw_question_ids: Any) -> list[str]:
    if not isinstance(raw_question_ids, list):
        return []
    existing = set(_build_question_lookup(paper).keys())
    ordered: list[str] = []
    for item in raw_question_ids:
        value = str(item).strip()
        if value and value in existing and value not in ordered:
            ordered.append(value)
    return ordered


def _collect_question_ids_for_sections(paper: ExamPaperDraft, target_sections: list[str]) -> list[str]:
    question_ids: list[str] = []
    allowed = set(target_sections)
    for section in paper.sections:
        if section.section_name not in allowed:
            continue
        for question in section.questions:
            question_ids.append(question.question_id)
    return question_ids


def _collect_regenerable_question_ids(paper: ExamPaperDraft) -> list[str]:
    question_ids: list[str] = []
    for section in paper.sections:
        for question in section.questions:
            if question.source_strategy != "question_bank_only":
                question_ids.append(question.question_id)
    return question_ids


def _annotate_questions_for_regeneration(
    paper: ExamPaperDraft,
    question_ids: list[str],
    *,
    reviewer: str,
    comment: str | None,
) -> ExamPaperDraft:
    updated = paper.model_copy(deep=True)
    allowed = set(question_ids)
    for section in updated.sections:
        for question in section.questions:
            if question.question_id not in allowed:
                continue
            if comment:
                question.review_comments = _dedupe_strings([*question.review_comments, comment])
            question.review_history.append(
                ExamQuestionReviewRecord(
                    reviewer=reviewer,
                    action="request_regeneration",
                    comment=comment,
                    timestamp=_now_iso(),
                )
            )
    return updated


async def _regenerate_question_batch(
    paper: ExamPaperDraft,
    question_ids: list[str],
    *,
    reviewer: str,
    comment: str | None,
) -> tuple[ExamPaperDraft, list[ExamQualityIssue]]:
    if not question_ids:
        return paper, []

    updated_paper = _annotate_questions_for_regeneration(
        paper,
        question_ids,
        reviewer=reviewer,
        comment=comment,
    )
    warnings: list[ExamQualityIssue] = []
    for question_id in question_ids:
        updated_paper, question_warnings = await regenerate_question_in_paper(
            updated_paper,
            question_id,
            review_comment=comment,
        )
        warnings.extend(question_warnings)
    return validate_exam_draft_quality(updated_paper), warnings


def _compute_request_totals_from_sections(sections: list[dict[str, Any]]) -> tuple[float, int]:
    total_score = 0.0
    total_questions = 0
    for section in sections:
        section_total = 0.0
        for requirement in section.get("question_requirements", []) or []:
            question_count = int(requirement.get("question_count") or 0)
            total_questions += question_count
            if requirement.get("total_score") is not None:
                section_total += float(requirement["total_score"])
            elif requirement.get("score_per_question") is not None:
                section_total += question_count * float(requirement["score_per_question"])
        if section.get("section_score") is None and section_total > 0:
            section["section_score"] = round(section_total, 4)
        total_score += float(section.get("section_score") or section_total or 0.0)
    return round(total_score, 4), total_questions


def _get_request_snapshot(paper: ExamPaperDraft) -> dict[str, Any]:
    snapshot = getattr(paper, "request_snapshot", None)
    if not snapshot:
        raise ValueError("当前草案缺少 request_snapshot，无法执行蓝图重规划。")
    if not isinstance(snapshot, dict):
        raise ValueError("request_snapshot 结构非法。")
    return copy.deepcopy(snapshot)


def _inherit_paper_memory(source_paper: ExamPaperDraft, target_paper: ExamPaperDraft) -> ExamPaperDraft:
    target_paper.revision_round = getattr(source_paper, "revision_round", 0)
    target_paper.paper_level_guidance = list(getattr(source_paper, "paper_level_guidance", []) or [])
    target_paper.feedback_history = list(getattr(source_paper, "feedback_history", []) or [])
    target_paper.generation_notes = _dedupe_strings(
        [
            *getattr(source_paper, "generation_notes", []),
            *getattr(target_paper, "generation_notes", []),
        ]
    )
    return target_paper


def _build_section_replan_messages(
    paper: ExamPaperDraft,
    teacher_feedback: str,
    target_sections: list[str],
    paper_level_guidance: list[str],
) -> list[dict[str, str]]:
    request_snapshot = _get_request_snapshot(paper)
    source_sections = [
        section
        for section in request_snapshot.get("sections", [])
        if section.get("section_name") in set(target_sections)
    ]
    system_prompt = """
你是“AI 组卷蓝图重规划 Agent”。

任务：根据教师反馈，仅重写命中的 section 蓝图，而不是整张卷。

只允许输出一个 JSON 对象，格式：
{
  "summary": "本轮大题级蓝图调整摘要",
  "sections": [完整 section 对象列表]
}

要求：
1. 只返回 target_sections 对应的完整 section 定义。
2. section 必须符合标准组卷请求里的结构，保留 question_requirements。
3. 如果教师反馈要求降难、换题型比例、减少开放题，要体现在 question_requirements、instructions、section_score 中。
4. 不要输出解释性文本。
""".strip()

    user_prompt = f"""
教师反馈：
{teacher_feedback}

命中的大题：
{json.dumps(target_sections, ensure_ascii=False)}

当前整卷指导：
{json.dumps(paper_level_guidance, ensure_ascii=False)}

原始组卷请求中的目标 section：
{json.dumps(source_sections, ensure_ascii=False, indent=2)}

最近反馈记忆：
{json.dumps(_build_feedback_history_lines(paper), ensure_ascii=False, indent=2)}
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_paper_replan_messages(
    paper: ExamPaperDraft,
    teacher_feedback: str,
    paper_level_guidance: list[str],
) -> list[dict[str, str]]:
    request_snapshot = _get_request_snapshot(paper)
    system_prompt = """
你是“AI 组卷全卷二次规划 Agent”。

任务：根据教师最新反馈，重写整张卷子的蓝图请求，再交给后续出题层重新生成。

只允许输出一个 JSON 对象，格式：
{
  "summary": "整卷蓝图重规划摘要",
  "exam_request": {完整标准组卷请求对象}
}

要求：
1. 必须输出完整 exam_request，而不是局部字段。
2. 必须保持当前系统可执行的结构化组卷 schema。
3. 需要根据教师反馈主动调整大题结构、题型比例、分值分布、notes_to_generator。
4. 默认继续使用 ai_generate_only。
5. 不要输出任何额外说明。
""".strip()

    user_prompt = f"""
教师反馈：
{teacher_feedback}

当前持续生效的整卷指导：
{json.dumps(paper_level_guidance, ensure_ascii=False)}

原始标准组卷请求：
{json.dumps(request_snapshot, ensure_ascii=False, indent=2)}

最近反馈记忆：
{json.dumps(_build_feedback_history_lines(paper), ensure_ascii=False, indent=2)}
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _replan_sections_and_regenerate_paper(
    paper: ExamPaperDraft,
    *,
    teacher_feedback: str,
    target_sections: list[str],
    paper_level_guidance: list[str],
    cfg: Config,
    llm_provider: str,
    llm_model: str,
) -> tuple[ExamPaperDraft, list[ExamQualityIssue], str]:
    logger.info(
        "Starting section-level replan | target_sections=%s | guidance=%s",
        target_sections,
        paper_level_guidance,
    )
    base_request_payload = _get_request_snapshot(paper)
    messages = _build_section_replan_messages(
        paper,
        teacher_feedback,
        target_sections,
        paper_level_guidance,
    )
    raw_response = await create_chat_completion(
        messages=messages,
        model=llm_model,
        llm_provider=llm_provider,
        temperature=0.1,
        max_tokens=2600,
        llm_kwargs=_get_exam_llm_kwargs(cfg, llm_provider),
        reasoning_effort=_get_exam_reasoning_effort(cfg, llm_provider),
    )
    logger.info("LLM section replan response: %s", _preview_text(raw_response))
    parsed = _extract_json_payload(raw_response)
    section_summary = str(parsed.get("summary") or "已完成命中大题的蓝图重规划。")
    raw_sections = parsed.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("section 重规划结果缺少 sections。")

    validated_sections = [
        PaperSectionRequirement.model_validate(item).model_dump(mode="json")
        for item in raw_sections
    ]
    target_set = set(target_sections)
    new_sections: list[dict[str, Any]] = []
    replaced = set()
    for section in base_request_payload.get("sections", []) or []:
        section_name = section.get("section_name")
        replacement = next(
            (candidate for candidate in validated_sections if candidate.get("section_name") == section_name),
            None,
        )
        if section_name in target_set and replacement is not None:
            new_sections.append(replacement)
            replaced.add(section_name)
        else:
            new_sections.append(section)
    for section in validated_sections:
        section_name = section.get("section_name")
        if section_name in target_set and section_name not in replaced:
            new_sections.append(section)
    total_score, total_questions = _compute_request_totals_from_sections(new_sections)
    logger.info(
        "Section replan merged | sections=%s | total_score=%s | target_question_count=%s",
        len(new_sections),
        total_score,
        total_questions,
    )
    base_request_payload["sections"] = new_sections
    base_request_payload["total_score"] = total_score
    base_request_payload["target_question_count"] = total_questions
    notes = str(base_request_payload.get("notes_to_generator") or "").strip()
    merged_guidance = "；".join(paper_level_guidance)
    if merged_guidance:
        base_request_payload["notes_to_generator"] = "；".join(
            _dedupe_strings([notes, merged_guidance])
        )
    exam_request = ExamPaperRequest.model_validate(base_request_payload)
    validation = validate_exam_paper_request_model(exam_request)
    if not validation["valid"]:
        logger.warning("Section replan validation failed: %s", validation)
        raise ValueError("section 重规划后的组卷请求未通过业务校验。")
    logger.info(
        "Section replan validation passed, starting draft regeneration | total_sections=%s | target_question_count=%s",
        len(exam_request.sections),
        exam_request.target_question_count,
    )
    regenerated_paper = await generate_exam_preview_paper(exam_request, validation)
    logger.info(
        "Section-level regeneration completed | generation_stage=%s | section_count=%s",
        regenerated_paper.generation_stage,
        len(regenerated_paper.sections),
    )
    regenerated_paper = _inherit_paper_memory(paper, regenerated_paper)
    return regenerated_paper, [], section_summary


async def _replan_whole_paper_and_regenerate(
    paper: ExamPaperDraft,
    *,
    teacher_feedback: str,
    paper_level_guidance: list[str],
    cfg: Config,
    llm_provider: str,
    llm_model: str,
) -> tuple[ExamPaperDraft, list[ExamQualityIssue], str]:
    logger.info(
        "Starting paper-level replan | guidance=%s | current_revision_round=%s",
        paper_level_guidance,
        getattr(paper, "revision_round", 0),
    )
    messages = _build_paper_replan_messages(
        paper,
        teacher_feedback,
        paper_level_guidance,
    )
    raw_response = await create_chat_completion(
        messages=messages,
        model=llm_model,
        llm_provider=llm_provider,
        temperature=0.1,
        max_tokens=4200,
        llm_kwargs=_get_exam_llm_kwargs(cfg, llm_provider),
        reasoning_effort=_get_exam_reasoning_effort(cfg, llm_provider),
    )
    logger.info("LLM paper replan response: %s", _preview_text(raw_response))
    parsed = _extract_json_payload(raw_response)
    paper_summary = str(parsed.get("summary") or "已完成整卷蓝图重规划。")
    exam_request_payload = parsed.get("exam_request")
    if not isinstance(exam_request_payload, dict):
        raise ValueError("整卷重规划结果缺少 exam_request。")
    base_request = _get_request_snapshot(paper)
    merged_payload = _deep_merge(base_request, exam_request_payload)
    sections = list(merged_payload.get("sections", []) or [])
    total_score, total_questions = _compute_request_totals_from_sections(sections)
    logger.info(
        "Paper replan merged | sections=%s | total_score=%s | target_question_count=%s",
        len(sections),
        total_score,
        total_questions,
    )
    if sections:
        merged_payload["sections"] = sections
        merged_payload["total_score"] = total_score
        merged_payload["target_question_count"] = total_questions
    exam_request = ExamPaperRequest.model_validate(merged_payload)
    validation = validate_exam_paper_request_model(exam_request)
    if not validation["valid"]:
        logger.warning("Paper replan validation failed: %s", validation)
        raise ValueError("整卷蓝图重规划后的组卷请求未通过业务校验。")
    logger.info(
        "Paper replan validation passed, starting draft regeneration | total_sections=%s | target_question_count=%s",
        len(exam_request.sections),
        exam_request.target_question_count,
    )
    regenerated_paper = await generate_exam_preview_paper(exam_request, validation)
    logger.info(
        "Paper-level regeneration completed | generation_stage=%s | section_count=%s",
        regenerated_paper.generation_stage,
        len(regenerated_paper.sections),
    )
    regenerated_paper = _inherit_paper_memory(paper, regenerated_paper)
    return regenerated_paper, [], paper_summary


def _build_teacher_feedback_messages(payload: ExamTeacherFeedbackRequest) -> list[dict[str, str]]:
    system_prompt = """
你是“AI 组卷审核 Agent”。

你的职责是读取教师对整份试卷的自然语言反馈，并结合历史反馈，决定应该对哪些题执行什么动作，以及是否需要进行整卷级二次规划。

只允许输出一个 JSON 对象，格式如下：
{
  "summary": "本轮反馈处理摘要",
  "strategy": "no_change | question_level_edit | section_level_regenerate | paper_level_regenerate",
  "target_sections": ["需要整体重做的大题名称"],
  "target_question_ids": ["需要定点修改的题目ID"],
  "paper_level_guidance": ["新的整卷指导 1", "新的整卷指导 2"],
  "actions": [
    {
      "question_id": "题目ID",
      "action": "approve | reject | request_regeneration",
      "comment": "给执行层的明确说明"
    }
  ]
}

必须遵守：
1. 先决定改动范围，再决定动作。
2. 如果只需要改几道题，strategy = question_level_edit，并用 target_question_ids + actions 指明。
3. 如果某个大题整体有问题，strategy = section_level_regenerate，并用 target_sections 指明。
4. 如果整卷方向都错了，strategy = paper_level_regenerate。
5. actions 只挑真正需要改动的题，数量不要超过 max_actions。
6. 如果教师反馈是“换题 / 降难 / 改风格 / 缩短题干 / 改作文要求”，优先使用 request_regeneration。
7. reject 和 request_regeneration 必须带 comment。
8. 不要捏造不存在的 question_id 或 section 名称。
9. 若整卷无需调整，strategy = no_change，actions 返回空数组。
""".strip()

    user_prompt = f"""
教师反馈：
{payload.teacher_feedback}

最大允许动作数：
{payload.max_actions}

当前试卷题目概览：
{json.dumps(_build_question_overview_lines(payload.paper), ensure_ascii=False, indent=2)}

当前持续生效的整卷指导：
{json.dumps(getattr(payload.paper, "paper_level_guidance", []) or [], ensure_ascii=False, indent=2)}

最近几轮教师反馈记忆：
{json.dumps(_build_feedback_history_lines(payload.paper), ensure_ascii=False, indent=2)}

请基于教师反馈，尽量用最少动作完成本轮修改。
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def apply_teacher_feedback_with_llm(
    payload: ExamTeacherFeedbackRequest,
) -> ExamTeacherFeedbackResult:
    """让 LLM 决定整卷反馈应该转成哪些题目动作，再复用现有审核链路执行。"""

    cfg = _get_llm_config()
    llm_provider, llm_model = _get_exam_planning_model(cfg)

    try:
        messages = _build_teacher_feedback_messages(payload)
        raw_response = await create_chat_completion(
            messages=messages,
            model=llm_model,
            llm_provider=llm_provider,
            temperature=0.1,
            max_tokens=2200,
            llm_kwargs=_get_exam_llm_kwargs(cfg, llm_provider),
            reasoning_effort=_get_exam_reasoning_effort(cfg, llm_provider),
        )
        logger.info("LLM teacher feedback response: %s", _preview_text(raw_response))
        parsed = _extract_json_payload(raw_response)
    except (ValueError, RuntimeError) as exc:
        return ExamTeacherFeedbackResult(
            valid=False,
            summary="",
            planned_actions=[],
            errors=[_issue("error", "teacher_feedback_planning_failed", f"教师反馈 LLM 规划失败：{exc}", "teacher_feedback")],
            warnings=[],
            paper=None,
        )

    reviewer = (payload.reviewer or "frontend_teacher").strip()
    summary = str(parsed.get("summary") or "已根据教师反馈生成处理计划。")
    strategy = _normalize_feedback_strategy(str(parsed.get("strategy") or "question_level_edit"))
    target_sections = _normalize_target_sections(payload.paper, parsed.get("target_sections"))
    target_question_ids = _normalize_target_question_ids(payload.paper, parsed.get("target_question_ids"))
    raw_guidance = parsed.get("paper_level_guidance") or []
    if not isinstance(raw_guidance, list):
        raw_guidance = []
    paper_level_guidance = _dedupe_strings([str(item) for item in raw_guidance])
    raw_actions = parsed.get("actions") or []
    if not isinstance(raw_actions, list):
        raw_actions = []

    logger.info(
        "Teacher feedback plan normalized | strategy=%s | target_sections=%s | target_question_ids=%s | guidance=%s | raw_actions=%s",
        strategy,
        target_sections,
        target_question_ids,
        paper_level_guidance,
        len(raw_actions),
    )

    planned_actions: list[ExamTeacherFeedbackPlannedAction] = []
    errors: list[ExamQualityIssue] = []
    for index, item in enumerate(raw_actions[: payload.max_actions]):
        if not isinstance(item, dict):
            errors.append(_issue("error", "invalid_planned_action", "LLM 规划出的动作不是对象。", f"actions[{index}]"))
            continue
        try:
            planned_actions.append(ExamTeacherFeedbackPlannedAction.model_validate(item))
        except ValidationError as exc:
            errors.append(
                _issue(
                    "error",
                    "invalid_planned_action",
                    exc.errors()[0].get("msg", "LLM 规划的动作结构不合法。"),
                    f"actions[{index}]",
                )
            )

    if errors:
        return ExamTeacherFeedbackResult(
            valid=False,
            summary=summary,
            strategy=strategy,
            target_sections=target_sections,
            target_question_ids=target_question_ids,
            paper_level_guidance=paper_level_guidance,
            planned_actions=planned_actions,
            errors=errors,
            warnings=[],
            paper=None,
        )

    if strategy == "no_change":
        updated_paper = _append_feedback_memory_to_paper(
            payload.paper,
            reviewer=reviewer,
            teacher_feedback=payload.teacher_feedback,
            strategy=strategy,
            summary=summary,
            target_sections=target_sections,
            target_question_ids=target_question_ids,
            paper_level_guidance=paper_level_guidance,
            planned_actions=[],
        )
        return ExamTeacherFeedbackResult(
            valid=True,
            summary=summary,
            strategy=strategy,
            target_sections=target_sections,
            target_question_ids=target_question_ids,
            paper_level_guidance=paper_level_guidance,
            planned_actions=[],
            errors=[],
            warnings=[
                _issue(
                    "warning",
                    "no_feedback_actions",
                    "LLM 认为当前整卷无需执行修改动作。",
                    "actions",
                ),
                *(
                    [
                        _issue(
                            "warning",
                            "ignored_actions_under_no_change",
                            "LLM 给出了动作，但 strategy=no_change，执行层已忽略这些动作。",
                            "actions",
                        )
                    ]
                    if planned_actions
                    else []
                ),
            ],
            paper=updated_paper,
        )

    execution_warnings: list[ExamQualityIssue] = []
    updated_paper: ExamPaperDraft | None = payload.paper
    execution_errors: list[ExamQualityIssue] = []

    if strategy == "question_level_edit":
        effective_actions = planned_actions
        if not effective_actions and target_question_ids:
            effective_actions = [
                ExamTeacherFeedbackPlannedAction(
                    question_id=question_id,
                    action="request_regeneration",
                    comment="根据教师整卷反馈，需要定点调整该题。",
                )
                for question_id in target_question_ids
            ]
        review_request = ExamPaperReviewRequest(
            paper=payload.paper,
            reviewer=payload.reviewer,
            actions=[
                ExamQuestionReviewAction(
                    question_id=action.question_id,
                    action=action.action,
                    comment=_merge_teacher_comment(action.comment, strategy, paper_level_guidance),
                    reviewer=payload.reviewer,
                )
                for action in effective_actions
            ],
        )
        review_result = await apply_exam_review_actions(review_request)
        updated_paper = review_result.paper
        execution_warnings.extend(review_result.warnings)
        execution_errors.extend(review_result.errors)
        planned_actions = effective_actions
        target_question_ids = [action.question_id for action in effective_actions]
    elif strategy == "section_level_regenerate":
        effective_sections = target_sections or _get_existing_section_names(payload.paper)[:1]
        try:
            updated_paper, regeneration_warnings, replan_summary = await _replan_sections_and_regenerate_paper(
                payload.paper,
                teacher_feedback=payload.teacher_feedback,
                target_sections=effective_sections,
                paper_level_guidance=paper_level_guidance,
                cfg=cfg,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        except Exception as exc:
            return ExamTeacherFeedbackResult(
                valid=False,
                summary=summary,
                strategy=strategy,
                target_sections=effective_sections,
                target_question_ids=target_question_ids,
                paper_level_guidance=paper_level_guidance,
                planned_actions=planned_actions,
                errors=[
                    _issue(
                        "error",
                        "section_replan_failed",
                        f"大题级蓝图重规划失败：{exc}",
                        "teacher_feedback",
                    )
                ],
                warnings=execution_warnings,
                paper=None,
            )
        execution_warnings.extend(regeneration_warnings)
        summary = replan_summary or summary
        target_sections = effective_sections
        target_question_ids = _collect_question_ids_for_sections(updated_paper, effective_sections)
        planned_actions = [
            ExamTeacherFeedbackPlannedAction(
                question_id=question_id,
                action="request_regeneration",
                comment="根据 section 级蓝图重规划重新生成。",
            )
            for question_id in target_question_ids
        ]
    elif strategy == "paper_level_regenerate":
        try:
            updated_paper, regeneration_warnings, replan_summary = await _replan_whole_paper_and_regenerate(
                payload.paper,
                teacher_feedback=payload.teacher_feedback,
                paper_level_guidance=paper_level_guidance,
                cfg=cfg,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        except Exception as exc:
            return ExamTeacherFeedbackResult(
                valid=False,
                summary=summary,
                strategy=strategy,
                target_sections=target_sections,
                target_question_ids=target_question_ids,
                paper_level_guidance=paper_level_guidance,
                planned_actions=planned_actions,
                errors=[
                    _issue(
                        "error",
                        "paper_replan_failed",
                        f"整卷蓝图重规划失败：{exc}",
                        "teacher_feedback",
                    )
                ],
                warnings=execution_warnings,
                paper=None,
            )
        execution_warnings.extend(regeneration_warnings)
        summary = replan_summary or summary
        target_sections = _get_existing_section_names(updated_paper)
        target_question_ids = _collect_regenerable_question_ids(updated_paper)
        planned_actions = [
            ExamTeacherFeedbackPlannedAction(
                question_id=question_id,
                action="request_regeneration",
                comment="根据整卷蓝图重规划重新生成。",
            )
            for question_id in target_question_ids
        ]

    if execution_errors or updated_paper is None:
        return ExamTeacherFeedbackResult(
            valid=False,
            summary=summary,
            strategy=strategy,
            target_sections=target_sections,
            target_question_ids=target_question_ids,
            paper_level_guidance=paper_level_guidance,
            planned_actions=planned_actions,
            errors=execution_errors or [
                _issue("error", "teacher_feedback_execution_failed", "教师反馈执行失败。", "teacher_feedback")
            ],
            warnings=execution_warnings,
            paper=None,
        )

    updated_paper = _append_feedback_memory_to_paper(
        updated_paper,
        reviewer=reviewer,
        teacher_feedback=payload.teacher_feedback,
        strategy=strategy,
        summary=summary,
        target_sections=target_sections,
        target_question_ids=target_question_ids,
        paper_level_guidance=paper_level_guidance,
        planned_actions=planned_actions,
    )
    return ExamTeacherFeedbackResult(
        valid=True,
        summary=summary,
        strategy=strategy,
        target_sections=target_sections,
        target_question_ids=target_question_ids,
        paper_level_guidance=paper_level_guidance,
        planned_actions=planned_actions,
        errors=[],
        warnings=execution_warnings,
        paper=updated_paper,
    )
