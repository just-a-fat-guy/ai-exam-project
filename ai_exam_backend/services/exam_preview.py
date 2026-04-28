"""AI 组卷预览服务。

这一层的目标不是直接生成正式试卷，而是基于“已通过校验的组卷请求”
先构造一份稳定的蓝图预览，帮助前端和后续业务层回答三个问题：

1. 这份组卷请求在结构上会落成什么样的试卷骨架？
2. 每个大题、每个题型会拆出多少题目槽位？
3. 当前生成策略会把哪些题位优先交给题库，哪些题位允许 AI 补题？
"""

from __future__ import annotations

from typing import Any

from schemas import ExamPaperRequest, PaperGenerationMode


def _round_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _infer_source_strategy(mode: PaperGenerationMode, allow_ai_generation: bool) -> str:
    """根据全局模式和题型级配置推断单题位来源策略。"""

    if mode == PaperGenerationMode.QuestionBankOnly:
        return "question_bank_only"
    if mode == PaperGenerationMode.AIGenerateOnly:
        return "ai_generate_only"
    if allow_ai_generation:
        return "question_bank_first_then_ai"
    return "question_bank_only"


def _build_generation_notes(exam_request: ExamPaperRequest) -> list[str]:
    """生成给前端展示的策略说明。"""

    notes: list[str] = []
    mode = exam_request.generation_policy.mode

    if mode == PaperGenerationMode.Hybrid:
        notes.append("当前是混合组卷模式：优先题库抽题，不足时允许 AI 补题。")
    elif mode == PaperGenerationMode.QuestionBankOnly:
        notes.append("当前是纯题库模式：所有题位都必须由题库提供。")
    else:
        notes.append("当前是纯 AI 出题模式：题库范围不会作为主要来源。")

    if exam_request.generation_policy.include_answers:
        notes.append("预期正式生成时同时输出标准答案。")
    if exam_request.generation_policy.include_explanations:
        notes.append("预期正式生成时同时输出题目解析。")
    if exam_request.generation_policy.deduplicate_questions:
        notes.append("后续正式组卷时会执行去重策略，避免题目重复。")
    if exam_request.notes_to_generator:
        notes.append(f"补充要求：{exam_request.notes_to_generator}")

    return notes


def _build_review_checklist(exam_request: ExamPaperRequest) -> list[str]:
    """把审核开关翻译成前端容易展示的清单。"""

    review = exam_request.review_requirement
    if not review.enabled:
        return ["当前请求未启用人工审核流程。"]

    checklist = ["教师审核试卷结构与题型分布。"]
    if review.require_answer_review:
        checklist.append("教师审核标准答案。")
    if review.require_explanation_review:
        checklist.append("教师审核题目解析。")
    if review.require_knowledge_point_review:
        checklist.append("教师确认知识点标注是否准确。")
    if review.reviewer_notes:
        checklist.append(f"审核备注：{review.reviewer_notes}")
    return checklist


def build_exam_paper_preview(
    exam_request: ExamPaperRequest,
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    """基于组卷请求构造试卷蓝图预览。

    参数：
    - exam_request: 已通过 schema 解析的请求对象
    - validation_result: 前一步业务校验结果，用于附带摘要和警告信息
    """

    mode = exam_request.generation_policy.mode
    sections_preview: list[dict[str, Any]] = []

    global_slot_index = 1
    question_bank_slot_count = 0
    ai_enabled_slot_count = 0
    estimated_total_score = 0.0

    for section_index, section in enumerate(exam_request.sections, start=1):
        section_slots: list[dict[str, Any]] = []
        requirement_groups: list[dict[str, Any]] = []
        section_total_score = 0.0
        section_score_fully_computable = True

        for requirement_index, requirement in enumerate(section.question_requirements, start=1):
            score_per_question = requirement.score_per_question
            if score_per_question is None and requirement.total_score is not None:
                score_per_question = requirement.total_score / requirement.question_count

            if score_per_question is None:
                section_score_fully_computable = False

            source_strategy = _infer_source_strategy(mode, requirement.allow_ai_generation)
            requirement_slot_start = global_slot_index
            requirement_total_score = 0.0

            for slot_index in range(1, requirement.question_count + 1):
                slot_score = _round_score(score_per_question)
                if slot_score is not None:
                    section_total_score += slot_score
                    estimated_total_score += slot_score
                    requirement_total_score += slot_score

                if source_strategy == "question_bank_only":
                    question_bank_slot_count += 1
                elif source_strategy == "ai_generate_only":
                    ai_enabled_slot_count += 1
                else:
                    question_bank_slot_count += 1
                    ai_enabled_slot_count += 1

                section_slots.append(
                    {
                        "slot_id": f"S{section_index}-Q{global_slot_index}",
                        "section_slot_index": slot_index,
                        "global_slot_index": global_slot_index,
                        "question_type": requirement.question_type.value,
                        "difficulty": requirement.preferred_difficulty.value
                        if requirement.preferred_difficulty
                        else None,
                        "score": slot_score,
                        "knowledge_points": requirement.knowledge_points,
                        "constraints": requirement.constraints,
                        "source_strategy": source_strategy,
                        "allow_ai_generation": requirement.allow_ai_generation,
                        "max_candidates": exam_request.generation_policy.max_candidate_questions_per_slot,
                    }
                )
                global_slot_index += 1

            requirement_groups.append(
                {
                    "group_id": f"S{section_index}-R{requirement_index}",
                    "question_type": requirement.question_type.value,
                    "question_count": requirement.question_count,
                    "score_per_question": _round_score(score_per_question),
                    "computed_total_score": _round_score(requirement_total_score)
                    if score_per_question is not None
                    else _round_score(requirement.total_score),
                    "difficulty": requirement.preferred_difficulty.value
                    if requirement.preferred_difficulty
                    else None,
                    "knowledge_points": requirement.knowledge_points,
                    "source_strategy": source_strategy,
                    "allow_ai_generation": requirement.allow_ai_generation,
                    "slot_range": {
                        "start": requirement_slot_start,
                        "end": global_slot_index - 1,
                    },
                }
            )

        sections_preview.append(
            {
                "section_name": section.section_name,
                "section_order": section.section_order or section_index,
                "instructions": section.instructions,
                "requested_section_score": _round_score(section.section_score),
                "computed_section_score": _round_score(section_total_score)
                if section_score_fully_computable
                else None,
                "question_slot_count": len(section_slots),
                "requirement_groups": requirement_groups,
                "question_slots": section_slots,
            }
        )

    return {
        "paper_title": exam_request.paper_title,
        "meta": {
            "subject": exam_request.subject.value,
            "school_stage": exam_request.school_stage.value,
            "grade": exam_request.grade,
            "exam_type": exam_request.exam_type,
            "term": exam_request.term,
            "language": exam_request.language,
            "duration_minutes": exam_request.duration_minutes,
        },
        "totals": {
            "requested_total_score": _round_score(exam_request.total_score),
            "estimated_total_score": _round_score(estimated_total_score),
            "requested_question_count": exam_request.target_question_count,
            "computed_question_count": global_slot_index - 1,
            "section_count": len(sections_preview),
            "question_bank_slot_count": question_bank_slot_count,
            "ai_enabled_slot_count": ai_enabled_slot_count,
        },
        "generation_policy": {
            "mode": mode.value,
            "allow_question_rewrite": exam_request.generation_policy.allow_question_rewrite,
            "allow_ai_generate_missing": exam_request.generation_policy.allow_ai_generate_missing,
            "deduplicate_questions": exam_request.generation_policy.deduplicate_questions,
            "include_answers": exam_request.generation_policy.include_answers,
            "include_explanations": exam_request.generation_policy.include_explanations,
            "output_formats": exam_request.output_formats,
        },
        "source_scope": {
            "question_bank_ids": exam_request.source_scope.question_bank_ids,
            "syllabus_ids": exam_request.source_scope.syllabus_ids,
            "document_ids": exam_request.source_scope.document_ids,
            "tags": exam_request.source_scope.tags,
        },
        "knowledge_points": [
            {
                "name": point.name,
                "required": point.required,
                "target_question_count": point.target_question_count,
                "weight": point.weight,
            }
            for point in exam_request.knowledge_points
        ],
        "sections": sections_preview,
        "generation_notes": _build_generation_notes(exam_request),
        "review_checklist": _build_review_checklist(exam_request),
        "validation_summary": validation_result.get("summary"),
        "warnings": validation_result.get("warnings", []),
    }
