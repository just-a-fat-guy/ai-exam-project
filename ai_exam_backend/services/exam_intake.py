"""自然语言组卷需求解析服务。

这一层的目标不是让用户先填完整结构化表单，而是先支持：

    “小学语文三年级下册期末考试试卷，难度一般”

这样的自然语言输入。

当前实现采取“轻抽取 + 模板补全”的策略：
1. 先从自然语言中抽取学科、学段、年级、考试类型、难度等关键信息
2. 再按学科 / 学段模板自动补全 section、题型和分值

这样做比直接让 LLM 一次性吐完整 ExamPaperRequest 更稳。
"""

from __future__ import annotations

import re
from typing import Any

from schemas import (
    DifficultyLevel,
    ExamNaturalLanguageParseResult,
    ExamNaturalLanguageRequest,
    ExamPaperRequest,
    ExamQualityIssue,
    KnowledgePointConstraint,
    PaperGenerationMode,
    PaperSectionRequirement,
    QuestionTypeRequirement,
    ReviewRequirement,
    SchoolStage,
    Subject,
    QuestionSourceScope,
    GenerationPolicy,
)


def _issue(level: str, code: str, message: str, path: str) -> ExamQualityIssue:
    return ExamQualityIssue(level=level, code=code, message=message, path=path)


SUBJECT_KEYWORDS: list[tuple[str, Subject]] = [
    ("语文", Subject.Chinese),
    ("数学", Subject.Math),
    ("英语", Subject.English),
    ("物理", Subject.Physics),
    ("化学", Subject.Chemistry),
    ("生物", Subject.Biology),
    ("历史", Subject.History),
    ("地理", Subject.Geography),
    ("政治", Subject.Politics),
    ("科学", Subject.Science),
]

EXAM_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("期末", "final"),
    ("期中", "midterm"),
    ("单元", "unit_test"),
    ("月考", "monthly_exam"),
    ("模拟", "mock_exam"),
    ("摸底", "diagnostic_test"),
]

DIFFICULTY_KEYWORDS: list[tuple[str, DifficultyLevel]] = [
    ("简单", DifficultyLevel.Easy),
    ("基础", DifficultyLevel.Easy),
    ("容易", DifficultyLevel.Easy),
    ("一般", DifficultyLevel.Medium),
    ("中等", DifficultyLevel.Medium),
    ("适中", DifficultyLevel.Medium),
    ("较难", DifficultyLevel.Hard),
    ("困难", DifficultyLevel.Hard),
    ("拔高", DifficultyLevel.Hard),
    ("压轴", DifficultyLevel.Hard),
]

CHINESE_NUMERAL_TO_INT = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _parse_compact_count_token(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)

    normalized = token.replace("两", "二")
    if normalized == "十":
        return 10
    if "十" in normalized:
        parts = normalized.split("十", 1)
        tens = CHINESE_NUMERAL_TO_INT.get(parts[0], 1 if parts[0] == "" else 0)
        ones = CHINESE_NUMERAL_TO_INT.get(parts[1], 0 if parts[1] == "" else 0)
        total = tens * 10 + ones
        return total if total > 0 else None

    return CHINESE_NUMERAL_TO_INT.get(normalized)


def _extract_subject(text: str) -> Subject | None:
    for keyword, subject in SUBJECT_KEYWORDS:
        if keyword in text:
            return subject
    return None


def _extract_exam_type(text: str) -> str:
    for keyword, exam_type in EXAM_TYPE_KEYWORDS:
        if keyword in text:
            return exam_type
    return "final" if "考试" in text else "unit_test"


def _extract_term(text: str) -> str | None:
    if any(keyword in text for keyword in ["下册", "下学期", "第二学期"]):
        return "spring"
    if any(keyword in text for keyword in ["上册", "上学期", "第一学期"]):
        return "autumn"
    return None


def _extract_difficulty(text: str) -> DifficultyLevel:
    for keyword, difficulty in DIFFICULTY_KEYWORDS:
        if keyword in text:
            return difficulty
    return DifficultyLevel.Medium


def _parse_primary_grade(text: str) -> tuple[SchoolStage, str] | None:
    match = re.search(r"([一二三四五六])年级", text)
    if match:
        grade_num = CHINESE_NUMERAL_TO_INT[match.group(1)]
        return SchoolStage.Primary, f"grade_{grade_num}"
    return None


def _parse_junior_grade(text: str) -> tuple[SchoolStage, str] | None:
    match = re.search(r"([七八九])年级", text)
    if match:
        grade_num = CHINESE_NUMERAL_TO_INT[match.group(1)]
        return SchoolStage.JuniorHigh, f"grade_{grade_num}"
    return None


def _parse_senior_grade(text: str) -> tuple[SchoolStage, str] | None:
    mapping = {"高一": "grade_10", "高二": "grade_11", "高三": "grade_12"}
    for keyword, grade in mapping.items():
        if keyword in text:
            return SchoolStage.SeniorHigh, grade
    return None


def _extract_stage_and_grade(text: str) -> tuple[SchoolStage, str] | tuple[None, None]:
    for parser in (_parse_primary_grade, _parse_junior_grade, _parse_senior_grade):
        parsed = parser(text)
        if parsed:
            return parsed

    if "小学" in text:
        return SchoolStage.Primary, "grade_unknown"
    if "初中" in text:
        return SchoolStage.JuniorHigh, "grade_unknown"
    if "高中" in text:
        return SchoolStage.SeniorHigh, "grade_unknown"

    return None, None


def _extract_total_score(text: str) -> int | None:
    match = re.search(r"(\d+)\s*分", text)
    if match:
        return int(match.group(1))
    return None


def _extract_duration_minutes(text: str) -> int | None:
    match = re.search(r"(\d+)\s*分钟", text)
    if match:
        return int(match.group(1))
    return None


def _extract_target_question_count(text: str) -> int | None:
    patterns = [
        r"共\s*([一二三四五六七八九十两\d]+)\s*(?:道|个)?(?:题目|题|小题)",
        r"生成\s*([一二三四五六七八九十两\d]+)\s*(?:道|个)?(?:题目|题|小题)",
        r"出\s*([一二三四五六七八九十两\d]+)\s*(?:道|个)?(?:题目|题|小题)",
        r"([一二三四五六七八九十两\d]+)\s*(?:道|个)?(?:题目|题|小题)(?:即可|就行|就好|左右)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        count = _parse_compact_count_token(match.group(1))
        if count and count > 0:
            return count
    return None


def _extract_balanced_section_preference(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "比例均衡",
            "均衡",
            "各半",
            "对半",
            "一半",
            "比例相同",
        ]
    )


def _default_total_score(subject: Subject, stage: SchoolStage) -> int:
    if subject == Subject.Math and stage in {SchoolStage.JuniorHigh, SchoolStage.SeniorHigh}:
        return 120
    if subject == Subject.Chinese and stage in {SchoolStage.JuniorHigh, SchoolStage.SeniorHigh}:
        return 120
    return 100


def _default_duration_minutes(subject: Subject, stage: SchoolStage) -> int:
    if stage == SchoolStage.Primary:
        return 90
    if subject in {Subject.Chinese, Subject.Math, Subject.English}:
        return 120
    return 90


def _allocate_scores(total_score: int, weights: list[int]) -> list[int]:
    allocated: list[int] = []
    remaining = total_score
    total_weight = sum(weights) or 1

    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            score = remaining
        else:
            score = max(1, round(total_score * weight / total_weight))
            if score >= remaining:
                score = max(1, remaining - (len(weights) - index - 1))
        allocated.append(score)
        remaining -= score

    return allocated


def _template_for_subject_stage(subject: Subject, stage: SchoolStage) -> list[dict[str, Any]]:
    if subject == Subject.Chinese and stage == SchoolStage.Primary:
        return [
            {
                "section_name": "基础积累",
                "instructions": "考查字词、句式和基础语言运用。",
                "weight": 25,
                "requirements": [
                    {"question_type": "fill_blank", "count": 6, "weight": 12},
                    {"question_type": "single_choice", "count": 4, "weight": 13},
                ],
            },
            {
                "section_name": "阅读理解",
                "instructions": "围绕课内外阅读材料进行理解与表达。",
                "weight": 35,
                "requirements": [
                    {"question_type": "reading_comprehension", "count": 2, "weight": 35},
                ],
            },
            {
                "section_name": "习作表达",
                "instructions": "按要求完成习作，表达完整，条理清楚。",
                "weight": 40,
                "requirements": [
                    {"question_type": "essay", "count": 1, "weight": 40},
                ],
            },
        ]

    if subject == Subject.Math and stage == SchoolStage.Primary:
        return [
            {
                "section_name": "基础题",
                "instructions": "考查基础概念和基本计算。",
                "weight": 36,
                "requirements": [
                    {"question_type": "single_choice", "count": 5, "weight": 10},
                    {"question_type": "fill_blank", "count": 5, "weight": 10},
                    {"question_type": "true_false", "count": 4, "weight": 16},
                ],
            },
            {
                "section_name": "计算与应用",
                "instructions": "要求写出必要计算步骤。",
                "weight": 64,
                "requirements": [
                    {"question_type": "calculation", "count": 4, "weight": 32},
                    {"question_type": "composite", "count": 2, "weight": 32},
                ],
            },
        ]

    if subject == Subject.Math and stage == SchoolStage.JuniorHigh:
        return [
            {
                "section_name": "基础题",
                "instructions": "考查基础知识与基本方法。",
                "weight": 40,
                "requirements": [
                    {"question_type": "single_choice", "count": 8, "weight": 20},
                    {"question_type": "fill_blank", "count": 6, "weight": 20},
                ],
            },
            {
                "section_name": "解答题",
                "instructions": "要求写出必要推理和计算过程。",
                "weight": 60,
                "requirements": [
                    {"question_type": "calculation", "count": 4, "weight": 28},
                    {"question_type": "composite", "count": 2, "weight": 32},
                ],
            },
        ]

    if subject == Subject.Chinese and stage == SchoolStage.JuniorHigh:
        return [
            {
                "section_name": "语言积累与运用",
                "instructions": "考查字词句、默写与语言表达基础。",
                "weight": 30,
                "requirements": [
                    {"question_type": "fill_blank", "count": 6, "weight": 16},
                    {"question_type": "single_choice", "count": 5, "weight": 14},
                ],
            },
            {
                "section_name": "阅读理解",
                "instructions": "包括现代文或文言文阅读。",
                "weight": 35,
                "requirements": [
                    {"question_type": "reading_comprehension", "count": 2, "weight": 35},
                ],
            },
            {
                "section_name": "写作表达",
                "instructions": "完成作文或较完整的表达任务。",
                "weight": 35,
                "requirements": [
                    {"question_type": "essay", "count": 1, "weight": 35},
                ],
            },
        ]

    return [
        {
            "section_name": "基础题",
            "instructions": "优先覆盖核心知识点，保证基础题占比。",
            "weight": 55,
            "requirements": [
                {"question_type": "single_choice", "count": 6, "weight": 20},
                {"question_type": "fill_blank", "count": 4, "weight": 15},
                {"question_type": "short_answer", "count": 3, "weight": 20},
            ],
        },
        {
            "section_name": "综合题",
            "instructions": "考查知识综合应用能力。",
            "weight": 45,
            "requirements": [
                {"question_type": "composite", "count": 2, "weight": 25},
                {"question_type": "case_analysis", "count": 1, "weight": 20},
            ],
        },
    ]


def _build_sections(
    *,
    subject: Subject,
    stage: SchoolStage,
    difficulty: DifficultyLevel,
    total_score: int,
    target_question_count: int | None = None,
    balance_sections: bool = False,
) -> tuple[list[PaperSectionRequirement], int]:
    section_templates = _template_for_subject_stage(subject, stage)
    section_scores = _allocate_scores(total_score, [item["weight"] for item in section_templates])
    sections: list[PaperSectionRequirement] = []
    final_question_count = 0

    requested_total_questions = (
        max(1, int(target_question_count))
        if target_question_count is not None
        else None
    )

    def allocate_counts(total: int, weights: list[int]) -> list[int]:
        if total <= 0 or not weights:
            return [0 for _ in weights]
        if total >= len(weights):
            base = [1 for _ in weights]
            remaining = total - len(weights)
            weighted_extra = _allocate_scores(remaining, weights) if remaining > 0 else [0 for _ in weights]
            return [base_count + extra for base_count, extra in zip(base, weighted_extra)]

        ranked_indexes = sorted(range(len(weights)), key=lambda idx: weights[idx], reverse=True)
        counts = [0 for _ in weights]
        for idx in ranked_indexes[:total]:
            counts[idx] = 1
        return counts

    if requested_total_questions is not None:
        section_weights = [1 for _ in section_templates] if balance_sections else [item["weight"] for item in section_templates]
        section_question_targets = allocate_counts(requested_total_questions, section_weights)
    else:
        section_question_targets = [None for _ in section_templates]

    for section_index, (section_template, section_score, section_question_target) in enumerate(
        zip(section_templates, section_scores, section_question_targets),
        start=1,
    ):
        requirement_templates = section_template["requirements"]
        requirement_scores = _allocate_scores(
            section_score,
            [item["weight"] for item in requirement_templates],
        )
        if section_question_target is not None:
            requirement_question_targets = allocate_counts(
                section_question_target,
                [item["weight"] for item in requirement_templates],
            )
        else:
            requirement_question_targets = [int(item["count"]) for item in requirement_templates]
        question_requirements: list[QuestionTypeRequirement] = []

        for requirement_template, requirement_score, requirement_question_count in zip(
            requirement_templates,
            requirement_scores,
            requirement_question_targets,
        ):
            question_count = int(requirement_question_count)
            if question_count <= 0:
                continue
            final_question_count += question_count
            score_per_question = (
                requirement_score / question_count
                if question_count > 0 and requirement_score % question_count == 0
                else None
            )
            question_requirements.append(
                QuestionTypeRequirement(
                    question_type=requirement_template["question_type"],
                    question_count=question_count,
                    score_per_question=score_per_question,
                    total_score=requirement_score,
                    preferred_difficulty=difficulty,
                    knowledge_points=[],
                    allow_ai_generation=True,
                    constraints=["避免超纲", "题意清晰", "答案尽量唯一"],
                )
            )

        sections.append(
            PaperSectionRequirement(
                section_name=section_template["section_name"],
                section_order=section_index,
                instructions=section_template["instructions"],
                section_score=section_score,
                question_requirements=question_requirements,
            )
        )

    return sections, final_question_count


def _build_paper_title(
    *,
    stage: SchoolStage,
    subject: Subject,
    grade: str,
    term: str | None,
    exam_type: str,
) -> str:
    stage_label_map = {
        SchoolStage.Primary: "小学",
        SchoolStage.JuniorHigh: "初中",
        SchoolStage.SeniorHigh: "高中",
        SchoolStage.University: "大学",
    }
    subject_label_map = {
        Subject.Chinese: "语文",
        Subject.Math: "数学",
        Subject.English: "英语",
        Subject.Physics: "物理",
        Subject.Chemistry: "化学",
        Subject.Biology: "生物",
        Subject.History: "历史",
        Subject.Geography: "地理",
        Subject.Politics: "政治",
        Subject.Science: "科学",
        Subject.Comprehensive: "综合",
        Subject.Other: "学科",
    }
    term_label_map = {"spring": "下册", "autumn": "上册"}
    exam_label_map = {
        "final": "期末考试试卷",
        "midterm": "期中考试试卷",
        "unit_test": "单元测验",
        "monthly_exam": "月考试卷",
        "mock_exam": "模拟试卷",
        "diagnostic_test": "摸底测试卷",
    }

    grade_label = grade.replace("grade_", "")
    return (
        f"{stage_label_map.get(stage, '')}{subject_label_map.get(subject, '学科')}"
        f"{grade_label}年级"
        f"{term_label_map.get(term, '')}"
        f"{exam_label_map.get(exam_type, '考试试卷')}"
    )


def parse_natural_exam_request(payload: ExamNaturalLanguageRequest) -> ExamNaturalLanguageParseResult:
    text = payload.user_request.strip()
    if not text:
        return ExamNaturalLanguageParseResult(
            valid=False,
            task_summary="自然语言组卷需求为空",
            assumptions=[],
            extracted={},
            exam_request=None,
            errors=[_issue("error", "empty_user_request", "请先输入组卷需求。", "user_request")],
        )

    subject = _extract_subject(text)
    if subject is None:
        return ExamNaturalLanguageParseResult(
            valid=False,
            task_summary=text,
            assumptions=[],
            extracted={},
            exam_request=None,
            errors=[_issue("error", "subject_not_found", "未识别出学科，请在需求中明确写出语文、数学等学科。", "user_request")],
        )

    stage, grade = _extract_stage_and_grade(text)
    if stage is None or grade is None:
        return ExamNaturalLanguageParseResult(
            valid=False,
            task_summary=text,
            assumptions=[],
            extracted={"subject": subject.value},
            exam_request=None,
            errors=[_issue("error", "grade_not_found", "未识别出学段或年级，请在需求中明确写出小学三年级、七年级、高一等信息。", "user_request")],
        )

    exam_type = _extract_exam_type(text)
    term = _extract_term(text)
    difficulty = _extract_difficulty(text)
    requested_question_count = _extract_target_question_count(text)
    balance_sections = _extract_balanced_section_preference(text)
    total_score = _extract_total_score(text) or _default_total_score(subject, stage)
    duration_minutes = _extract_duration_minutes(text) or _default_duration_minutes(subject, stage)
    sections, target_question_count = _build_sections(
        subject=subject,
        stage=stage,
        difficulty=difficulty,
        total_score=total_score,
        target_question_count=requested_question_count,
        balance_sections=balance_sections,
    )

    assumptions: list[str] = []
    if _extract_total_score(text) is None:
        assumptions.append(f"未明确总分，已按 {total_score} 分生成默认试卷结构。")
    if _extract_duration_minutes(text) is None:
        assumptions.append(f"未明确考试时长，已默认 {duration_minutes} 分钟。")
    if term is None:
        assumptions.append("未明确上下册/学期，默认不区分册别，只按当前学段学科模板组卷。")
    if requested_question_count is None:
        assumptions.append("未明确题目数量，已按当前学段学科模板生成默认题量。")
    else:
        assumptions.append(f"已根据自然语言要求，将题目总数控制为 {target_question_count} 题。")
    if balance_sections:
        assumptions.append("已根据“比例均衡”等表述，尽量让不同题型分区的题量分配更均衡。")
    assumptions.append("当前默认使用仅 AI 出题模式，不接入题库。")

    paper_title = _build_paper_title(
        stage=stage,
        subject=subject,
        grade=grade,
        term=term,
        exam_type=exam_type,
    )

    exam_request = ExamPaperRequest(
        paper_title=paper_title,
        subject=subject,
        school_stage=stage,
        grade=grade,
        exam_type=exam_type,
        term=term,
        language="zh-CN",
        duration_minutes=duration_minutes,
        total_score=total_score,
        target_question_count=target_question_count,
        knowledge_points=[],
        sections=sections,
        source_scope=QuestionSourceScope(),
        generation_policy=GenerationPolicy(
            mode=payload.generation_mode or PaperGenerationMode.AIGenerateOnly,
            allow_question_rewrite=False,
            allow_ai_generate_missing=True,
            deduplicate_questions=True,
            include_answers=payload.include_answers,
            include_explanations=payload.include_explanations,
            max_candidate_questions_per_slot=3,
        ),
        review_requirement=ReviewRequirement(
            enabled=True,
            require_answer_review=True,
            require_explanation_review=True,
            require_knowledge_point_review=False,
        ),
        notes_to_generator=text,
        output_formats=payload.output_formats or ["json", "docx"],
        metadata={
            "source": "natural_language_intake",
            "difficulty_preference": difficulty.value,
            "raw_user_request": text,
        },
    )

    return ExamNaturalLanguageParseResult(
        valid=True,
        task_summary=text,
        assumptions=assumptions,
        extracted={
            "subject": subject.value,
            "school_stage": stage.value,
            "grade": grade,
            "exam_type": exam_type,
            "term": term,
            "difficulty": difficulty.value,
            "total_score": total_score,
            "duration_minutes": duration_minutes,
            "requested_question_count": requested_question_count,
            "balanced_section_preference": balance_sections,
        },
        exam_request=exam_request.model_dump(mode="json"),
        errors=[],
    )
