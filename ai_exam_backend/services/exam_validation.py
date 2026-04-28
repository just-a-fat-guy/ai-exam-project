"""AI 组卷请求的业务校验服务。

注意区分两层校验：

1. Schema 校验
   由 Pydantic / FastAPI 负责，主要解决“字段类型对不对、必填项在不在”。

2. 业务校验
   由本文件负责，主要解决“字段组合以后是否自洽、是否符合组卷规则”。

例如：
- `question_count` 是不是正整数，属于 schema 校验
- 各大题题量之和是否等于全卷目标题量，属于业务校验
- 只允许题库抽题的模式下却没给题库范围，属于业务校验
"""

from __future__ import annotations

from typing import Any

from pydantic_core import ErrorDetails

from schemas import ExamPaperRequest, PaperGenerationMode


SUPPORTED_OUTPUT_FORMATS = {"json", "docx", "pdf", "md", "markdown"}


def _format_path(parts: tuple[Any, ...] | list[Any]) -> str:
    """把 Pydantic / 业务层的定位信息格式化成更稳定的字符串路径。

    例如：
    - ("sections", 0, "question_requirements", 1) -> "sections[0].question_requirements[1]"
    - [] -> "root"
    """

    if not parts:
        return "root"

    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path = f"{path}.{part}" if path else str(part)
    return path


def _issue(level: str, code: str, message: str, path: str = "root") -> dict[str, Any]:
    """统一构造错误 / 警告项，保证前端好消费。"""

    return {
        "level": level,
        "code": code,
        "message": message,
        "path": path,
    }


def _round_score(value: float | None) -> float | None:
    """分值类字段统一保留到 4 位小数，避免浮点噪音。"""

    if value is None:
        return None
    return round(value, 4)


def _normalize_output_formats(output_formats: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """标准化输出格式，并顺手产出非致命告警。

    这里不直接修改请求对象，而是返回一个“归一化后的副本数据”。
    """

    warnings: list[dict[str, Any]] = []
    normalized: list[str] = []
    seen: set[str] = set()

    for index, raw_format in enumerate(output_formats):
        candidate = raw_format.strip().lower()
        if candidate == "markdown":
            candidate = "md"

        if not candidate:
            warnings.append(
                _issue(
                    "warning",
                    "empty_output_format",
                    "发现空的输出格式项，已在归一化结果中忽略。",
                    f"output_formats[{index}]",
                )
            )
            continue

        if candidate in seen:
            warnings.append(
                _issue(
                    "warning",
                    "duplicate_output_format",
                    f"输出格式 '{candidate}' 重复出现，归一化结果中已去重。",
                    f"output_formats[{index}]",
                )
            )
            continue

        normalized.append(candidate)
        seen.add(candidate)

    return normalized, warnings


def build_exam_paper_schema_error_result(errors: list[ErrorDetails]) -> dict[str, Any]:
    """把 Pydantic 的 schema 校验错误转换成统一响应结构。

    验证接口的目标不是直接抛 422，而是稳定返回一份“可展示、可联调”的结果。
    """

    normalized_errors = [
        _issue(
            "error",
            "schema_validation_error",
            error.get("msg", "请求结构校验失败。"),
            _format_path(error.get("loc", ())),
        )
        for error in errors
    ]

    return {
        "valid": False,
        "schema_valid": False,
        "business_valid": False,
        "errors": normalized_errors,
        "warnings": [],
        "summary": None,
        "normalized_request": None,
    }


def validate_exam_paper_request_model(exam_request: ExamPaperRequest) -> dict[str, Any]:
    """对已通过 schema 解析的组卷请求做业务规则校验。

    这里关注的不是“字段能不能解析”，而是“字段组合以后是否自洽”。
    返回值会被前端直接消费，因此结构要尽量稳定、清晰。
    """

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    normalized_request = exam_request.model_dump(mode="json")
    normalized_formats, format_warnings = _normalize_output_formats(exam_request.output_formats)
    warnings.extend(format_warnings)
    normalized_request["output_formats"] = normalized_formats

    unsupported_formats = [
        fmt for fmt in normalized_formats if fmt not in SUPPORTED_OUTPUT_FORMATS
    ]
    for fmt in unsupported_formats:
        errors.append(
            _issue(
                "error",
                "unsupported_output_format",
                f"输出格式 '{fmt}' 当前后端不支持。",
                "output_formats",
            )
        )

    if not exam_request.sections:
        errors.append(
            _issue(
                "error",
                "empty_sections",
                "试卷结构不能为空，至少需要定义一个 section。",
                "sections",
            )
        )

    section_name_seen: set[str] = set()
    section_order_seen: set[int] = set()
    knowledge_point_mentions: set[str] = set()
    question_type_breakdown: dict[str, int] = {}

    total_question_count = 0
    computed_total_score = 0.0
    score_fully_computable = True

    for section_index, section in enumerate(exam_request.sections):
        section_path = f"sections[{section_index}]"

        normalized_name = section.section_name.strip().lower()
        if normalized_name in section_name_seen:
            warnings.append(
                _issue(
                    "warning",
                    "duplicate_section_name",
                    f"分区名称 '{section.section_name}' 重复出现，后续展示和审核时建议改成唯一名称。",
                    f"{section_path}.section_name",
                )
            )
        else:
            section_name_seen.add(normalized_name)

        if section.section_order is not None:
            if section.section_order in section_order_seen:
                warnings.append(
                    _issue(
                        "warning",
                        "duplicate_section_order",
                        f"section_order={section.section_order} 重复出现，后续排序可能不稳定。",
                        f"{section_path}.section_order",
                    )
                )
            else:
                section_order_seen.add(section.section_order)

        if not section.question_requirements:
            errors.append(
                _issue(
                    "error",
                    "empty_section_requirements",
                    f"分区 '{section.section_name}' 下没有任何题型要求。",
                    f"{section_path}.question_requirements",
                )
            )
            continue

        section_total_score = 0.0
        section_score_fully_computable = True

        for requirement_index, requirement in enumerate(section.question_requirements):
            requirement_path = f"{section_path}.question_requirements[{requirement_index}]"

            total_question_count += requirement.question_count
            question_type_breakdown[requirement.question_type.value] = (
                question_type_breakdown.get(requirement.question_type.value, 0)
                + requirement.question_count
            )

            for point in requirement.knowledge_points:
                knowledge_point_mentions.add(point.strip().lower())

            if (
                requirement.total_score is not None
                and requirement.score_per_question is not None
            ):
                implied_total = requirement.question_count * requirement.score_per_question
                if abs(implied_total - requirement.total_score) > 1e-6:
                    errors.append(
                        _issue(
                            "error",
                            "question_score_mismatch",
                            (
                                f"题型 '{requirement.question_type.value}' 的 total_score="
                                f"{requirement.total_score} 与 question_count * score_per_question="
                                f"{_round_score(implied_total)} 不一致。"
                            ),
                            requirement_path,
                        )
                    )

            requirement_total_score: float | None
            if requirement.total_score is not None:
                requirement_total_score = requirement.total_score
            elif requirement.score_per_question is not None:
                requirement_total_score = requirement.question_count * requirement.score_per_question
            else:
                requirement_total_score = None
                section_score_fully_computable = False
                score_fully_computable = False
                warnings.append(
                    _issue(
                        "warning",
                        "missing_question_score",
                        (
                            f"题型 '{requirement.question_type.value}' 没有提供 total_score，"
                            "也没有提供 score_per_question，无法精确推导该部分分值。"
                        ),
                        requirement_path,
                    )
                )

            if requirement_total_score is not None:
                section_total_score += requirement_total_score
                computed_total_score += requirement_total_score

            if (
                exam_request.generation_policy.mode == PaperGenerationMode.QuestionBankOnly
                and requirement.allow_ai_generation
            ):
                warnings.append(
                    _issue(
                        "warning",
                        "ai_generation_flag_ignored",
                        "当前是 question_bank_only 模式，该题型上的 allow_ai_generation 配置不会生效。",
                        f"{requirement_path}.allow_ai_generation",
                    )
                )

        if (
            section.section_score is not None
            and section_score_fully_computable
            and abs(section_total_score - section.section_score) > 1e-6
        ):
            errors.append(
                _issue(
                    "error",
                    "section_score_mismatch",
                    (
                        f"分区 '{section.section_name}' 的 section_score={section.section_score} "
                        f"与题型分值汇总={_round_score(section_total_score)} 不一致。"
                    ),
                    section_path,
                )
            )
        elif section.section_score is not None and not section_score_fully_computable:
            warnings.append(
                _issue(
                    "warning",
                    "section_score_not_fully_checkable",
                    (
                        f"分区 '{section.section_name}' 提供了 section_score，"
                        "但内部存在未标分值的题型，无法做完整一致性校验。"
                    ),
                    section_path,
                )
            )

    if (
        exam_request.target_question_count is not None
        and total_question_count != exam_request.target_question_count
    ):
        errors.append(
            _issue(
                "error",
                "question_count_mismatch",
                (
                    f"sections 中累计题量为 {total_question_count}，"
                    f"与 target_question_count={exam_request.target_question_count} 不一致。"
                ),
                "target_question_count",
            )
        )

    if score_fully_computable:
        if abs(computed_total_score - exam_request.total_score) > 1e-6:
            errors.append(
                _issue(
                    "error",
                    "paper_total_score_mismatch",
                    (
                        f"各 section 累计总分为 {_round_score(computed_total_score)}，"
                        f"与 total_score={exam_request.total_score} 不一致。"
                    ),
                    "total_score",
                )
            )
    else:
        warnings.append(
            _issue(
                "warning",
                "paper_total_score_not_fully_checkable",
                "部分题型缺少分值信息，无法对整张试卷的总分做完整一致性校验。",
                "total_score",
            )
        )

    if (
        exam_request.generation_policy.mode == PaperGenerationMode.QuestionBankOnly
        and not exam_request.source_scope.question_bank_ids
    ):
        errors.append(
            _issue(
                "error",
                "missing_question_bank_scope",
                "当前是 question_bank_only 模式，但 source_scope.question_bank_ids 为空。",
                "source_scope.question_bank_ids",
            )
        )

    if (
        exam_request.generation_policy.mode == PaperGenerationMode.AIGenerateOnly
        and not exam_request.generation_policy.allow_ai_generate_missing
    ):
        errors.append(
            _issue(
                "error",
                "invalid_ai_only_policy",
                "当前是 ai_generate_only 模式，allow_ai_generate_missing 不能为 false。",
                "generation_policy.allow_ai_generate_missing",
            )
        )

    if (
        exam_request.generation_policy.mode == PaperGenerationMode.AIGenerateOnly
        and exam_request.source_scope.question_bank_ids
    ):
        warnings.append(
            _issue(
                "warning",
                "question_bank_scope_unused",
                "当前是 ai_generate_only 模式，question_bank_ids 不会成为主要抽题来源。",
                "source_scope.question_bank_ids",
            )
        )

    if (
        not exam_request.review_requirement.enabled
        and (
            exam_request.review_requirement.require_answer_review
            or exam_request.review_requirement.require_explanation_review
            or exam_request.review_requirement.require_knowledge_point_review
        )
    ):
        warnings.append(
            _issue(
                "warning",
                "review_flags_ignored",
                "人工审核总开关已关闭，其余细分审核标志当前不会生效。",
                "review_requirement",
            )
        )

    required_points_without_mapping: list[str] = []
    for index, point in enumerate(exam_request.knowledge_points):
        normalized_point_name = point.name.strip().lower()
        if point.required and normalized_point_name not in knowledge_point_mentions:
            required_points_without_mapping.append(point.name)
            warnings.append(
                _issue(
                    "warning",
                    "knowledge_point_not_mapped",
                    f"必考知识点 '{point.name}' 没有在任何题型要求中显式出现。",
                    f"knowledge_points[{index}]",
                )
            )

    summary = {
        "paper_title": exam_request.paper_title,
        "subject": exam_request.subject.value,
        "school_stage": exam_request.school_stage.value,
        "section_count": len(exam_request.sections),
        "requested_total_score": _round_score(exam_request.total_score),
        "computed_total_score": _round_score(computed_total_score) if score_fully_computable else None,
        "target_question_count": exam_request.target_question_count,
        "computed_question_count": total_question_count,
        "knowledge_point_count": len(exam_request.knowledge_points),
        "required_knowledge_points_without_mapping": required_points_without_mapping,
        "question_type_breakdown": question_type_breakdown,
        "generation_mode": exam_request.generation_policy.mode.value,
        "output_formats": normalized_formats,
    }

    return {
        "valid": not errors,
        "schema_valid": True,
        "business_valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "normalized_request": normalized_request,
    }
