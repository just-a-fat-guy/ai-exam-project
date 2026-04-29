"""AI 组卷请求的数据结构定义。

这一层的目标不是立刻去“生成试卷”，而是先把后端真正要消费的组卷输入
稳定下来。只有请求结构清楚了，后面这些事情才能顺着做：

1. 前端组卷表单字段设计
2. 组卷规划 prompt 设计
3. 题库检索与抽题逻辑
4. AI 补题逻辑
5. 人工审核工作流

因此这里的设计原则是：

- 先结构化，而不是先 prompt 化
- 先把“约束条件”表达清楚，而不是先追求字段最少
- 允许后续扩展，但先给出一版足够可用的基础模型
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Subject(str, Enum):
    """学科枚举。

    第一版先覆盖常见学科；如果后面要支持更细的教研场景，
    可以继续扩展或改成字典配置驱动。
    """

    Chinese = "chinese"
    Math = "math"
    English = "english"
    Physics = "physics"
    Chemistry = "chemistry"
    Biology = "biology"
    History = "history"
    Geography = "geography"
    Politics = "politics"
    Science = "science"
    Comprehensive = "comprehensive"
    Other = "other"


class SchoolStage(str, Enum):
    """学段枚举。"""

    Primary = "primary"
    JuniorHigh = "junior_high"
    SeniorHigh = "senior_high"
    University = "university"
    Vocational = "vocational"
    AdultEducation = "adult_education"
    Other = "other"


class DifficultyLevel(str, Enum):
    """题目难度档位。"""

    Easy = "easy"
    Medium = "medium"
    Hard = "hard"


class QuestionType(str, Enum):
    """题型枚举。

    这里不是穷举一切可能题型，而是先覆盖最常见的出卷场景。
    """

    SingleChoice = "single_choice"
    MultipleChoice = "multiple_choice"
    TrueFalse = "true_false"
    FillBlank = "fill_blank"
    ShortAnswer = "short_answer"
    Essay = "essay"
    Calculation = "calculation"
    CaseAnalysis = "case_analysis"
    ReadingComprehension = "reading_comprehension"
    Cloze = "cloze"
    Translation = "translation"
    Practical = "practical"
    Composite = "composite"


class PaperGenerationMode(str, Enum):
    """组卷来源策略。

    - question_bank_only: 只允许题库抽题
    - ai_generate_only: 只允许 AI 直接出题
    - hybrid: 先题库抽题，不足部分允许 AI 补题
    """

    QuestionBankOnly = "question_bank_only"
    AIGenerateOnly = "ai_generate_only"
    Hybrid = "hybrid"


class KnowledgePointConstraint(BaseModel):
    """知识点约束。

    用于表达“这套卷子必须覆盖什么知识点，以及覆盖优先级如何”。
    """

    name: str = Field(..., description="知识点名称，例如：一元二次方程、文言文阅读。")
    required: bool = Field(default=True, description="是否必须覆盖该知识点。")
    weight: float | None = Field(
        default=None,
        ge=0,
        description="知识点权重，可用于后续蓝图规划或抽题优先级分配。",
    )
    target_question_count: int | None = Field(
        default=None,
        ge=0,
        description="期望该知识点覆盖的题目数量。",
    )
    notes: str | None = Field(
        default=None,
        description="对该知识点的额外说明，例如只考基础题、避免竞赛题。",
    )


class QuestionTypeRequirement(BaseModel):
    """单个题型的组卷要求。"""

    question_type: QuestionType = Field(..., description="题型。")
    question_count: int = Field(..., ge=1, description="该题型题目数量。")
    score_per_question: float | None = Field(
        default=None,
        ge=0,
        description="每题分值；如果为空，可由 total_score 或后续规划推导。",
    )
    total_score: float | None = Field(
        default=None,
        ge=0,
        description="该题型总分。",
    )
    preferred_difficulty: DifficultyLevel | None = Field(
        default=None,
        description="该题型整体偏向的难度档位。",
    )
    knowledge_points: list[str] = Field(
        default_factory=list,
        description="该题型优先覆盖的知识点列表。",
    )
    allow_ai_generation: bool = Field(
        default=True,
        description="该题型在题库不足时，是否允许 AI 直接补题。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="附加约束，例如避免偏题、避免超纲、答案唯一等。",
    )


class PaperSectionRequirement(BaseModel):
    """试卷大题 / 分区要求。"""

    section_name: str = Field(..., description="大题名称，例如：选择题、填空题、阅读理解。")
    section_order: int | None = Field(
        default=None,
        ge=1,
        description="大题顺序；前端或后端可根据该值稳定排序。",
    )
    instructions: str | None = Field(
        default=None,
        description="该大题给学生的作答说明。",
    )
    section_score: float | None = Field(
        default=None,
        ge=0,
        description="该大题总分。",
    )
    question_requirements: list[QuestionTypeRequirement] = Field(
        default_factory=list,
        description="该大题下的题型规划。",
    )


class QuestionSourceScope(BaseModel):
    """题目来源范围约束。"""

    question_bank_ids: list[str] = Field(
        default_factory=list,
        description="允许参与抽题的题库 ID 列表。",
    )
    syllabus_ids: list[str] = Field(
        default_factory=list,
        description="允许参与知识点约束的考纲 / 课程标准 ID 列表。",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="教师上传文档或教材资料 ID 列表。",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="题库标签过滤，例如：期中、基础题、压轴题。",
    )
    allowed_regions: list[str] = Field(
        default_factory=list,
        description="允许题目来源的地区范围。",
    )
    allowed_years: list[int] = Field(
        default_factory=list,
        description="允许抽题的年份范围。",
    )
    exclude_question_ids: list[str] = Field(
        default_factory=list,
        description="明确排除的题目 ID，常用于去重或避免重复出卷。",
    )


class GenerationPolicy(BaseModel):
    """组卷生成策略。"""

    mode: PaperGenerationMode = Field(
        default=PaperGenerationMode.Hybrid,
        description="整体组卷来源模式。",
    )
    allow_question_rewrite: bool = Field(
        default=False,
        description="是否允许对题库中的题目做轻度改写。",
    )
    allow_ai_generate_missing: bool = Field(
        default=True,
        description="当题库不足时，是否允许 AI 补题。",
    )
    deduplicate_questions: bool = Field(
        default=True,
        description="是否开启题目去重。",
    )
    include_answers: bool = Field(
        default=True,
        description="是否要求同时生成标准答案。",
    )
    include_explanations: bool = Field(
        default=True,
        description="是否要求同时生成解析。",
    )
    max_candidate_questions_per_slot: int = Field(
        default=5,
        ge=1,
        description="每个题目槽位最多保留多少候选题，方便后续审核或 rerank。",
    )


class ReviewRequirement(BaseModel):
    """人工审核要求。"""

    enabled: bool = Field(default=True, description="是否启用人工审核流程。")
    require_answer_review: bool = Field(default=True, description="是否必须审核答案。")
    require_explanation_review: bool = Field(default=True, description="是否必须审核解析。")
    require_knowledge_point_review: bool = Field(
        default=False,
        description="是否要求教师确认知识点标注。",
    )
    reviewer_notes: str | None = Field(
        default=None,
        description="给审核人的附加说明。",
    )


class ExamPaperRequest(BaseModel):
    """AI 组卷主请求模型。

    这就是后面前端提交给后端的核心请求结构。
    它表达的不是一句自然语言问题，而是一整组组卷约束。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "paper_title": "2026年春季九年级数学单元测验",
                "subject": "math",
                "school_stage": "junior_high",
                "grade": "grade_9",
                "term": "spring",
                "exam_type": "unit_test",
                "language": "zh-CN",
                "duration_minutes": 90,
                "total_score": 120,
                "target_question_count": 22,
                "knowledge_points": [
                    {
                        "name": "一元二次方程",
                        "required": True,
                        "target_question_count": 6,
                    },
                    {
                        "name": "二次函数",
                        "required": True,
                        "target_question_count": 8,
                    },
                ],
                "sections": [
                    {
                        "section_name": "选择题",
                        "section_order": 1,
                        "section_score": 40,
                        "question_requirements": [
                            {
                                "question_type": "single_choice",
                                "question_count": 10,
                                "score_per_question": 4,
                                "preferred_difficulty": "easy",
                                "allow_ai_generation": False,
                            }
                        ],
                    },
                    {
                        "section_name": "解答题",
                        "section_order": 2,
                        "section_score": 80,
                        "question_requirements": [
                            {
                                "question_type": "calculation",
                                "question_count": 4,
                                "total_score": 32,
                                "preferred_difficulty": "medium",
                            },
                            {
                                "question_type": "case_analysis",
                                "question_count": 2,
                                "total_score": 48,
                                "preferred_difficulty": "hard",
                            },
                        ],
                    },
                ],
                "source_scope": {
                    "question_bank_ids": ["bank_math_junior"],
                    "syllabus_ids": ["syllabus_math_grade9"],
                    "exclude_question_ids": [],
                },
                "generation_policy": {
                    "mode": "hybrid",
                    "allow_question_rewrite": False,
                    "allow_ai_generate_missing": True,
                    "deduplicate_questions": True,
                    "include_answers": True,
                    "include_explanations": True,
                },
                "review_requirement": {
                    "enabled": True,
                    "require_answer_review": True,
                    "require_explanation_review": True,
                },
                "notes_to_generator": "整体难度前易后难，避免超纲内容。",
                "output_formats": ["json", "docx"],
            }
        }
    )

    paper_title: str = Field(..., description="试卷标题。")
    subject: Subject = Field(..., description="学科。")
    school_stage: SchoolStage = Field(..., description="学段。")
    grade: str = Field(..., description="年级标识，例如 grade_6、grade_9、grade_12。")
    exam_type: str = Field(..., description="考试类型，例如 unit_test、midterm、final。")
    term: str | None = Field(default=None, description="学期，例如 spring、autumn。")
    language: str = Field(default="zh-CN", description="试卷输出语言。")
    region: str | None = Field(default=None, description="地区信息，可用于题目风格或题库过滤。")
    duration_minutes: int | None = Field(
        default=None,
        ge=1,
        description="考试时长（分钟）。",
    )
    total_score: float = Field(..., gt=0, description="试卷总分。")
    target_question_count: int | None = Field(
        default=None,
        ge=1,
        description="目标题目总数；有些场景也可只依赖 sections 自动推导。",
    )
    knowledge_points: list[KnowledgePointConstraint] = Field(
        default_factory=list,
        description="全卷层面的知识点覆盖要求。",
    )
    sections: list[PaperSectionRequirement] = Field(
        default_factory=list,
        description="试卷结构规划。",
    )
    source_scope: QuestionSourceScope = Field(
        default_factory=QuestionSourceScope,
        description="题目来源范围约束。",
    )
    generation_policy: GenerationPolicy = Field(
        default_factory=GenerationPolicy,
        description="组卷生成策略。",
    )
    review_requirement: ReviewRequirement = Field(
        default_factory=ReviewRequirement,
        description="人工审核要求。",
    )
    notes_to_generator: str | None = Field(
        default=None,
        description="给组卷引擎或大模型的补充说明。",
    )
    output_formats: list[str] = Field(
        default_factory=lambda: ["json"],
        description="期望输出格式，例如 json / docx / pdf。",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="预留扩展字段，用于挂业务侧自定义元信息。",
    )


class ExamNaturalLanguageRequest(BaseModel):
    """面向前端自然语言入口的轻量请求。"""

    user_request: str = Field(..., min_length=1, description="用户自然语言组卷需求。")
    generation_mode: PaperGenerationMode = Field(
        default=PaperGenerationMode.AIGenerateOnly,
        description="默认使用纯 AI 出题。",
    )
    include_answers: bool = Field(default=True, description="是否包含答案。")
    include_explanations: bool = Field(default=True, description="是否包含解析。")
    output_formats: list[str] = Field(
        default_factory=lambda: ["json", "docx"],
        description="期望输出格式。",
    )


class ExamQuestionOption(BaseModel):
    """试卷草案中的题目选项结构。"""

    label: str = Field(..., description="选项标签，例如 A / B / C / D。")
    content: str = Field(..., description="选项内容。")
    is_correct: bool | None = Field(
        default=None,
        description="是否为正确选项；非选择类题目可为空。",
    )


class ExamQualityIssue(BaseModel):
    """题目或试卷级质量问题。"""

    level: Literal["error", "warning"] = Field(..., description="问题级别。")
    code: str = Field(..., description="问题代码。")
    message: str = Field(..., description="问题说明。")
    path: str = Field(..., description="定位路径。")


class ExamNaturalLanguageParseResult(BaseModel):
    """自然语言组卷需求解析结果。"""

    valid: bool = Field(..., description="是否成功解析成可执行组卷请求。")
    task_summary: str = Field(..., description="给前端展示的摘要。")
    assumptions: list[str] = Field(
        default_factory=list,
        description="系统自动补全时采用的默认假设。",
    )
    extracted: dict[str, Any] = Field(
        default_factory=dict,
        description="从自然语言中抽取出的关键信息。",
    )
    exam_request: dict[str, Any] | None = Field(
        default=None,
        description="补全后的标准组卷请求；失败时为空。",
    )
    errors: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="解析失败时的错误列表。",
    )


class ExamQuestionReviewRecord(BaseModel):
    """单题审核历史记录。"""

    reviewer: str = Field(..., description="审核人。")
    action: Literal["approve", "reject", "request_regeneration"] = Field(
        ...,
        description="审核动作。",
    )
    comment: str | None = Field(default=None, description="审核备注。")
    timestamp: str = Field(..., description="动作时间戳。")


class ExamQuestionSnapshot(BaseModel):
    """用于记录题目某一时刻的核心内容快照。"""

    stem: str = Field(..., description="题干快照。")
    options: list[ExamQuestionOption] = Field(
        default_factory=list,
        description="选项快照。",
    )
    reference_answer: str | list[str] | None = Field(
        default=None,
        description="参考答案快照。",
    )
    explanation: str | None = Field(
        default=None,
        description="解析快照。",
    )
    knowledge_points: list[str] = Field(
        default_factory=list,
        description="知识点快照。",
    )


class ExamQuestionRegenerationDiff(BaseModel):
    """记录最近一次单题重生成前后的差异。"""

    previous: ExamQuestionSnapshot = Field(..., description="重生成前的题目快照。")
    current: ExamQuestionSnapshot = Field(..., description="重生成后的题目快照。")
    comment: str | None = Field(default=None, description="触发重生成时的审核备注。")
    regenerated_at: str = Field(..., description="重生成完成时间。")


class ExamDraftQuestion(BaseModel):
    """试卷草案中的单题结构。

    注意：
    当前阶段这份结构用于“预览草案”，重点是把题目级 JSON 结构先稳定下来。
    后面即使接入真实题库或 LLM 出题，这个输出模型也尽量保持不变。
    """

    question_id: str = Field(..., description="草案题目 ID。")
    slot_id: str = Field(..., description="来源于蓝图中的题位 ID。")
    order: int = Field(..., ge=1, description="题目在整张试卷中的顺序号。")
    section_order: int = Field(..., ge=1, description="所属大题顺序。")
    section_name: str = Field(..., description="所属大题名称。")
    question_type: QuestionType = Field(..., description="题型。")
    difficulty: DifficultyLevel | None = Field(
        default=None,
        description="题目难度。",
    )
    score: float | None = Field(default=None, ge=0, description="题目分值。")
    source_strategy: str = Field(..., description="当前题位的来源策略。")
    draft_status: Literal["template_preview", "generated_preview", "pending_regeneration"] = Field(
        default="template_preview",
        description="草案状态。当前第一版接口默认返回 template_preview。",
    )
    review_status: Literal["pending_review", "reviewed", "rejected"] = Field(
        default="pending_review",
        description="人工审核状态。",
    )
    knowledge_points: list[str] = Field(
        default_factory=list,
        description="题目关联知识点。",
    )
    stem: str = Field(..., description="题干。")
    options: list[ExamQuestionOption] = Field(
        default_factory=list,
        description="选项列表；非选择题可为空。",
    )
    reference_answer: str | list[str] | None = Field(
        default=None,
        description="参考答案。",
    )
    explanation: str | None = Field(
        default=None,
        description="参考解析。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="继承自题型要求的附加约束。",
    )
    quality_flags: list[str] = Field(
        default_factory=list,
        description="质量标记，例如 preview_only / missing_score / missing_knowledge_points。",
    )
    quality_issues: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="单题质量校验结果。",
    )
    review_comments: list[str] = Field(
        default_factory=list,
        description="审核备注列表。",
    )
    review_history: list[ExamQuestionReviewRecord] = Field(
        default_factory=list,
        description="审核历史记录。",
    )
    last_regeneration_diff: ExamQuestionRegenerationDiff | None = Field(
        default=None,
        description="最近一次重生成前后的题目差异；未发生重生成时为空。",
    )


class ExamDraftSection(BaseModel):
    """试卷草案中的大题结构。"""

    section_name: str = Field(..., description="大题名称。")
    section_order: int = Field(..., ge=1, description="大题顺序。")
    instructions: str | None = Field(default=None, description="作答说明。")
    requested_section_score: float | None = Field(
        default=None,
        ge=0,
        description="请求中给定的大题总分。",
    )
    computed_section_score: float | None = Field(
        default=None,
        ge=0,
        description="根据题目草案推导出的当前大题总分。",
    )
    question_count: int = Field(..., ge=0, description="该大题题目数量。")
    questions: list[ExamDraftQuestion] = Field(
        default_factory=list,
        description="该大题下的题目草案列表。",
    )


class ExamPaperDraft(BaseModel):
    """试卷草案输出模型。

    这份模型的定位是：
    - 让前端能够展示“题目级”的试卷草稿
    - 让后端后续接真实题库 / LLM 出题时，有稳定输出契约
    - 让人工审核流可以直接围绕这份结构继续扩展
    """

    paper_id: str = Field(..., description="草案试卷 ID。")
    paper_title: str = Field(..., description="试卷标题。")
    generation_stage: Literal["template_preview", "generated_preview", "mixed_preview"] = Field(
        default="template_preview",
        description="当前生成阶段，可表示模板预览、真实生成预览或混合预览。",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="试卷元信息，例如学科、年级、时长。",
    )
    totals: dict[str, Any] = Field(
        default_factory=dict,
        description="总分、题量、题位统计信息。",
    )
    generation_policy: dict[str, Any] = Field(
        default_factory=dict,
        description="生成策略快照。",
    )
    source_scope: dict[str, Any] = Field(
        default_factory=dict,
        description="题目来源范围快照。",
    )
    request_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="生成这份草案时使用的标准 ExamPaperRequest 快照，供后续二次规划复用。",
    )
    knowledge_points: list[dict[str, Any]] = Field(
        default_factory=list,
        description="知识点覆盖快照。",
    )
    sections: list[ExamDraftSection] = Field(
        default_factory=list,
        description="试卷大题及题目草案。",
    )
    generation_notes: list[str] = Field(
        default_factory=list,
        description="生成说明。",
    )
    review_checklist: list[str] = Field(
        default_factory=list,
        description="审核清单。",
    )
    quality_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="整张试卷的质量校验汇总。",
    )
    review_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="整张试卷的审核状态汇总。",
    )
    revision_round: int = Field(
        default=0,
        ge=0,
        description="教师反馈迭代轮次，从 0 开始。",
    )
    paper_level_guidance: list[str] = Field(
        default_factory=list,
        description="当前持续生效的整卷级指导，用于后续重生成和再规划。",
    )
    feedback_history: list["ExamTeacherFeedbackMemoryRecord"] = Field(
        default_factory=list,
        description="整卷级教师反馈 / agent 规划记忆历史。",
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="非致命告警。",
    )


class ExamPaperDraftResult(BaseModel):
    """生成试卷草案接口的统一返回结构。"""

    valid: bool = Field(..., description="请求是否通过验证并成功生成草案。")
    validation: dict[str, Any] = Field(
        default_factory=dict,
        description="验证结果快照。",
    )
    paper: ExamPaperDraft | None = Field(
        default=None,
        description="试卷草案；验证失败时为空。",
    )


class ExamGenerationTaskEvent(BaseModel):
    """异步组卷任务的进度事件。"""

    event_id: str = Field(..., description="事件 ID。")
    timestamp: str = Field(..., description="事件时间。")
    level: Literal["info", "warning", "error", "success"] = Field(
        default="info",
        description="事件级别。",
    )
    stage: str = Field(..., description="事件阶段标识。")
    message: str = Field(..., description="给前端展示的进度消息。")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="事件附加元信息，例如 slot_id、题型、状态等。",
    )


class ExamGenerationTaskProgress(BaseModel):
    """异步组卷任务的进度快照。"""

    total_slots: int = Field(default=0, ge=0, description="总题位数。")
    completed_slots: int = Field(default=0, ge=0, description="已处理完成的题位数。")
    generated_slots: int = Field(default=0, ge=0, description="成功生成题位数。")
    template_slots: int = Field(default=0, ge=0, description="模板回退题位数。")
    pending_regeneration_slots: int = Field(default=0, ge=0, description="待重生成题位数。")
    latest_message: str | None = Field(default=None, description="最新一条进度说明。")


class ExamGenerationTaskSnapshot(BaseModel):
    """异步组卷任务状态快照。"""

    task_id: str = Field(..., description="任务 ID。")
    status: Literal["queued", "running", "completed", "failed"] = Field(
        default="queued",
        description="任务状态。",
    )
    task_summary: str = Field(..., description="任务摘要。")
    created_at: str = Field(..., description="任务创建时间。")
    updated_at: str = Field(..., description="任务最近更新时间。")
    progress: ExamGenerationTaskProgress = Field(
        default_factory=ExamGenerationTaskProgress,
        description="进度快照。",
    )
    events: list[ExamGenerationTaskEvent] = Field(
        default_factory=list,
        description="进度事件列表。",
    )
    validation: dict[str, Any] = Field(
        default_factory=dict,
        description="创建任务时的校验结果快照。",
    )
    paper: ExamPaperDraft | None = Field(
        default=None,
        description="任务完成后的试卷草案。",
    )
    error: str | None = Field(
        default=None,
        description="任务失败时的错误说明。",
    )


class ExamTeacherFeedbackPlannedAction(BaseModel):
    """LLM 基于教师自然语言反馈规划出的动作。"""

    question_id: str = Field(..., description="目标题目 ID。")
    action: Literal["approve", "reject", "request_regeneration"] = Field(
        ...,
        description="LLM 建议执行的动作。",
    )
    comment: str | None = Field(
        default=None,
        description="动作原因或重生成指令。",
    )


class ExamTeacherFeedbackMemoryRecord(BaseModel):
    """整卷级教师反馈记忆记录。"""

    reviewer: str = Field(..., description="反馈人。")
    teacher_feedback: str = Field(..., description="教师原始反馈。")
    strategy: Literal["no_change", "question_level_edit", "section_level_regenerate", "paper_level_regenerate"] = Field(
        ...,
        description="LLM 对本轮反馈选择的处理策略。",
    )
    summary: str = Field(..., description="本轮处理摘要。")
    target_sections: list[str] = Field(
        default_factory=list,
        description="本轮策略命中的 section 名称。",
    )
    target_question_ids: list[str] = Field(
        default_factory=list,
        description="本轮策略命中的 question_id 列表。",
    )
    paper_level_guidance: list[str] = Field(
        default_factory=list,
        description="沉淀下来的全卷级指导语句，供后续轮次继续参考。",
    )
    planned_actions: list[ExamTeacherFeedbackPlannedAction] = Field(
        default_factory=list,
        description="本轮计划执行的题目动作列表。",
    )
    timestamp: str = Field(..., description="记录时间。")


class ExamTeacherFeedbackRequest(BaseModel):
    """教师整卷反馈请求。

    这不是“点按钮审核单题”，而是让老师用自然语言说：
    - “整体偏难，把应用题降一点”
    - “阅读理解第二题换一道更基础的”
    - “作文题太开放，改成半命题”

    后端再交给 LLM 决定要改哪些题、怎么改。
    """

    paper: ExamPaperDraft = Field(..., description="当前试卷草案。")
    teacher_feedback: str = Field(..., min_length=1, description="教师的自然语言反馈。")
    reviewer: str | None = Field(default=None, description="反馈人。")
    max_actions: int = Field(
        default=4,
        ge=1,
        le=12,
        description="LLM 本轮最多允许规划多少个动作，避免一次改动过大。",
    )


class ExamTeacherFeedbackResult(BaseModel):
    """教师整卷反馈处理结果。"""

    valid: bool = Field(..., description="反馈处理是否成功。")
    summary: str = Field(default="", description="LLM 对本轮反馈的处理摘要。")
    strategy: Literal["no_change", "question_level_edit", "section_level_regenerate", "paper_level_regenerate"] = Field(
        default="question_level_edit",
        description="本轮反馈采用的处理策略。",
    )
    target_sections: list[str] = Field(
        default_factory=list,
        description="本轮策略命中的 section 名称。",
    )
    target_question_ids: list[str] = Field(
        default_factory=list,
        description="本轮策略命中的 question_id 列表。",
    )
    paper_level_guidance: list[str] = Field(
        default_factory=list,
        description="本轮反馈沉淀出的全卷指导。",
    )
    planned_actions: list[ExamTeacherFeedbackPlannedAction] = Field(
        default_factory=list,
        description="LLM 决定执行的题目动作列表。",
    )
    errors: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="反馈处理级错误。",
    )
    warnings: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="反馈处理级警告。",
    )
    paper: ExamPaperDraft | None = Field(
        default=None,
        description="应用反馈动作后的最新试卷草案。",
    )


class ExamQuestionReviewAction(BaseModel):
    """单题审核动作请求。"""

    question_id: str = Field(..., description="目标题目 ID。")
    action: Literal["approve", "reject", "request_regeneration"] = Field(
        ...,
        description="审核动作。",
    )
    comment: str | None = Field(default=None, description="审核备注。")
    reviewer: str | None = Field(default=None, description="审核人。")


class ExamPaperReviewRequest(BaseModel):
    """人工审核动作请求。"""

    paper: ExamPaperDraft = Field(..., description="当前试卷草案。")
    actions: list[ExamQuestionReviewAction] = Field(
        default_factory=list,
        description="本次要应用的审核动作列表。",
    )
    reviewer: str | None = Field(default=None, description="默认审核人。")


class ExamPaperReviewResult(BaseModel):
    """人工审核动作响应。"""

    valid: bool = Field(..., description="动作请求是否有效。")
    errors: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="审核动作级错误。",
    )
    warnings: list[ExamQualityIssue] = Field(
        default_factory=list,
        description="审核动作级警告。",
    )
    applied_action_count: int = Field(
        default=0,
        ge=0,
        description="成功应用的审核动作数。",
    )
    paper: ExamPaperDraft | None = Field(
        default=None,
        description="应用动作后的试卷草案。",
    )


ExamPaperDraft.model_rebuild()
