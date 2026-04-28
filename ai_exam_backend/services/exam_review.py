"""AI 组卷人工审核动作服务。"""

from __future__ import annotations

from datetime import datetime, timezone

from schemas import (
    ExamPaperDraft,
    ExamPaperReviewRequest,
    ExamPaperReviewResult,
    ExamQualityIssue,
    ExamQuestionReviewRecord,
)

from .exam_draft import regenerate_question_in_paper
from .exam_quality import validate_exam_draft_quality


def _issue(level: str, code: str, message: str, path: str) -> ExamQualityIssue:
    return ExamQualityIssue(level=level, code=code, message=message, path=path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _build_question_lookup(paper: ExamPaperDraft) -> dict[str, object]:
    lookup = {}
    for section in paper.sections:
        for question in section.questions:
            lookup[question.question_id] = question
    return lookup


async def apply_exam_review_actions(payload: ExamPaperReviewRequest) -> ExamPaperReviewResult:
    """对试卷草案应用人工审核动作。"""

    updated_paper = payload.paper.model_copy(deep=True)
    errors: list[ExamQualityIssue] = []
    warnings: list[ExamQualityIssue] = []
    question_lookup = _build_question_lookup(updated_paper)

    applied_action_count = 0

    for action_index, action in enumerate(payload.actions):
        path = f"actions[{action_index}]"
        question = question_lookup.get(action.question_id)
        if question is None:
            errors.append(
                _issue(
                    "error",
                    "question_not_found",
                    f"未找到 question_id={action.question_id} 对应的题目。",
                    f"{path}.question_id",
                )
            )
            continue

        if action.action in {"reject", "request_regeneration"} and not (action.comment and action.comment.strip()):
            errors.append(
                _issue(
                    "error",
                    "missing_review_comment",
                    f"{action.action} 动作必须附带审核备注，说明原因。",
                    f"{path}.comment",
                )
            )
            continue

        reviewer = (action.reviewer or payload.reviewer or "anonymous_reviewer").strip()
        comment = action.comment.strip() if action.comment else None

        if action.action == "approve":
            question.review_status = "reviewed"
            question.quality_flags = _dedupe_strings(
                [flag for flag in question.quality_flags if flag != "review_rejected"]
            )
        elif action.action == "reject":
            question.review_status = "rejected"
            question.quality_flags = _dedupe_strings([*question.quality_flags, "review_rejected"])
        elif action.action == "request_regeneration":
            question.review_status = "pending_review"
            question.draft_status = "pending_regeneration"
            question.quality_flags = _dedupe_strings(
                [*question.quality_flags, "review_requested_regeneration"]
            )
        else:
            warnings.append(
                _issue(
                    "warning",
                    "unknown_review_action",
                    f"未识别的审核动作：{action.action}",
                    f"{path}.action",
                )
            )
            continue

        if comment:
            question.review_comments = _dedupe_strings([*question.review_comments, comment])
        question.review_history.append(
            ExamQuestionReviewRecord(
                reviewer=reviewer,
                action=action.action,
                comment=comment,
                timestamp=_now_iso(),
            )
        )

        if action.action == "request_regeneration":
            updated_paper, regeneration_warnings = await regenerate_question_in_paper(
                updated_paper,
                action.question_id,
                review_comment=comment,
            )
            warnings.extend(regeneration_warnings)
            question_lookup = _build_question_lookup(updated_paper)

        applied_action_count += 1

    if errors:
        return ExamPaperReviewResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            applied_action_count=applied_action_count,
            paper=None,
        )

    return ExamPaperReviewResult(
        valid=True,
        errors=[],
        warnings=warnings,
        applied_action_count=applied_action_count,
        paper=validate_exam_draft_quality(updated_paper),
    )
