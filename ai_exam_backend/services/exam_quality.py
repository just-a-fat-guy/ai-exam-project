"""AI 组卷单题质量校验服务。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from schemas import ExamPaperDraft, ExamQualityIssue, QuestionType


CHOICE_OPTION_COUNT = {
    QuestionType.SingleChoice.value: 4,
    QuestionType.MultipleChoice.value: 4,
    QuestionType.TrueFalse.value: 2,
}


def _issue(level: str, code: str, message: str, path: str) -> ExamQualityIssue:
    return ExamQualityIssue(level=level, code=code, message=message, path=path)


def _normalize_flags(flags: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for flag in flags:
        if flag and flag not in seen:
            ordered.append(flag)
            seen.add(flag)
    return ordered


def _validate_question(
    question,
    *,
    path_prefix: str,
    require_answers: bool,
    require_explanations: bool,
) -> list[ExamQualityIssue]:
    issues: list[ExamQualityIssue] = []

    if not question.stem or not question.stem.strip():
        issues.append(_issue("error", "empty_stem", "题干为空。", f"{path_prefix}.stem"))
    elif "请围绕" in question.stem and "设计一道" in question.stem:
        issues.append(
            _issue(
                "warning",
                "template_like_stem",
                "题干仍然带有明显的模板痕迹，建议人工复审或重生成。",
                f"{path_prefix}.stem",
            )
        )

    if question.score is None:
        issues.append(_issue("warning", "missing_score", "题目分值缺失。", f"{path_prefix}.score"))
    elif question.score <= 0:
        issues.append(_issue("error", "invalid_score", "题目分值必须大于 0。", f"{path_prefix}.score"))

    if not question.knowledge_points:
        issues.append(
            _issue("warning", "missing_knowledge_points", "题目未标注知识点。", f"{path_prefix}.knowledge_points")
        )

    if require_answers and question.reference_answer in (None, "", []):
        issues.append(
            _issue("error", "missing_reference_answer", "当前策略要求输出答案，但该题缺少参考答案。", f"{path_prefix}.reference_answer")
        )

    if require_explanations and not (question.explanation and question.explanation.strip()):
        issues.append(
            _issue("warning", "missing_explanation", "当前策略要求输出解析，但该题缺少解析。", f"{path_prefix}.explanation")
        )

    if question.draft_status == "pending_regeneration":
        issues.append(
            _issue("warning", "pending_regeneration", "该题当前处于待重生成状态。", f"{path_prefix}.draft_status")
        )

    if question.question_type in CHOICE_OPTION_COUNT:
        expected_count = CHOICE_OPTION_COUNT[question.question_type]
        if len(question.options) != expected_count:
            issues.append(
                _issue(
                    "error",
                    "invalid_option_count",
                    f"{question.question_type} 题应包含 {expected_count} 个选项，当前为 {len(question.options)} 个。",
                    f"{path_prefix}.options",
                )
            )

        labels = [option.label for option in question.options if option.label]
        if len(set(labels)) != len(labels):
            issues.append(
                _issue("error", "duplicate_option_labels", "选项标签存在重复。", f"{path_prefix}.options")
            )

        for option_index, option in enumerate(question.options):
            if not option.content or not option.content.strip():
                issues.append(
                    _issue(
                        "error",
                        "empty_option_content",
                        "存在空的选项内容。",
                        f"{path_prefix}.options[{option_index}].content",
                    )
                )

        correct_count = sum(1 for option in question.options if option.is_correct)
        if question.question_type == QuestionType.SingleChoice.value and correct_count != 1:
            issues.append(
                _issue(
                    "error",
                    "single_choice_correct_count_invalid",
                    f"单选题必须且只能有 1 个正确选项，当前为 {correct_count} 个。",
                    f"{path_prefix}.options",
                )
            )
        if question.question_type == QuestionType.MultipleChoice.value and correct_count < 2:
            issues.append(
                _issue(
                    "warning",
                    "multiple_choice_correct_count_low",
                    f"多选题通常应至少有 2 个正确选项，当前为 {correct_count} 个。",
                    f"{path_prefix}.options",
                )
            )
        if question.question_type == QuestionType.TrueFalse.value and correct_count != 1:
            issues.append(
                _issue(
                    "error",
                    "true_false_correct_count_invalid",
                    f"判断题必须且只能有 1 个正确选项，当前为 {correct_count} 个。",
                    f"{path_prefix}.options",
                )
            )
    else:
        if question.options:
            issues.append(
                _issue(
                    "warning",
                    "unexpected_options",
                    "非选择题通常不应携带 options。",
                    f"{path_prefix}.options",
                )
            )

    return issues


def validate_exam_draft_quality(
    paper: ExamPaperDraft,
    *,
    require_answers: bool | None = None,
    require_explanations: bool | None = None,
) -> ExamPaperDraft:
    """对试卷草案做单题和整卷质量校验，并回写质量汇总。"""

    updated_paper = paper.model_copy(deep=True)
    require_answers = (
        updated_paper.generation_policy.get("include_answers", True)
        if require_answers is None
        else require_answers
    )
    require_explanations = (
        updated_paper.generation_policy.get("include_explanations", True)
        if require_explanations is None
        else require_explanations
    )

    error_question_count = 0
    warning_question_count = 0
    total_issue_count = 0
    pending_regeneration_count = 0
    generated_question_count = 0
    template_question_count = 0
    paper_issues: list[ExamQualityIssue] = []
    paper_score_sum = 0.0
    score_fully_known = True

    for section_index, section in enumerate(updated_paper.sections):
        section_score_sum = 0.0
        section_score_fully_known = True

        for question_index, question in enumerate(section.questions):
            path_prefix = f"sections[{section_index}].questions[{question_index}]"
            issues = _validate_question(
                question,
                path_prefix=path_prefix,
                require_answers=require_answers,
                require_explanations=require_explanations,
            )
            question.quality_issues = issues
            total_issue_count += len(issues)

            if any(issue.level == "error" for issue in issues):
                error_question_count += 1
            if any(issue.level == "warning" for issue in issues):
                warning_question_count += 1

            derived_flags = list(question.quality_flags)
            if any(issue.level == "error" for issue in issues):
                derived_flags.append("quality_error")
            if any(issue.level == "warning" for issue in issues):
                derived_flags.append("quality_warning")
            question.quality_flags = _normalize_flags(derived_flags)

            if question.draft_status == "pending_regeneration":
                pending_regeneration_count += 1
            elif question.draft_status == "generated_preview":
                generated_question_count += 1
            else:
                template_question_count += 1

            if question.score is None:
                section_score_fully_known = False
                score_fully_known = False
            else:
                section_score_sum += question.score
                paper_score_sum += question.score

        section.computed_section_score = section_score_sum if section_score_fully_known else None
        if (
            section.requested_section_score is not None
            and section.computed_section_score is not None
            and abs(section.requested_section_score - section.computed_section_score) > 1e-6
        ):
            paper_issues.append(
                _issue(
                    "warning",
                    "section_score_mismatch",
                    (
                        f"大题 '{section.section_name}' 的请求分值为 {section.requested_section_score}，"
                        f"当前草案分值为 {section.computed_section_score}。"
                    ),
                    f"sections[{section_index}].computed_section_score",
                )
            )

    requested_total = updated_paper.totals.get("requested_total_score")
    if requested_total is not None and score_fully_known and abs(requested_total - paper_score_sum) > 1e-6:
        paper_issues.append(
            _issue(
                "warning",
                "paper_total_score_mismatch",
                f"整卷请求总分为 {requested_total}，当前草案分值为 {round(paper_score_sum, 4)}。",
                "totals.estimated_total_score",
            )
        )

    generated_stage_counter = Counter(question.draft_status for section in updated_paper.sections for question in section.questions)
    review_counter = Counter(question.review_status for section in updated_paper.sections for question in section.questions)

    updated_paper.quality_summary = {
        "total_questions": sum(section.question_count for section in updated_paper.sections),
        "error_question_count": error_question_count,
        "warning_question_count": warning_question_count,
        "total_issue_count": total_issue_count + len(paper_issues),
        "paper_level_issue_count": len(paper_issues),
        "pending_regeneration_count": pending_regeneration_count,
        "generated_question_count": generated_question_count,
        "template_question_count": template_question_count,
        "computed_total_score": round(paper_score_sum, 4) if score_fully_known else None,
        "score_fully_known": score_fully_known,
        "draft_status_breakdown": dict(generated_stage_counter),
    }
    updated_paper.review_summary = {
        "pending_review_count": review_counter.get("pending_review", 0),
        "reviewed_count": review_counter.get("reviewed", 0),
        "rejected_count": review_counter.get("rejected", 0),
    }
    updated_paper.warnings = [
        *updated_paper.warnings,
        *[issue.model_dump(mode="json") for issue in paper_issues],
    ]
    return updated_paper
