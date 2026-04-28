export type GenerationMode =
  | "question_bank_only"
  | "ai_generate_only"
  | "hybrid";

export type DifficultyLevel = "easy" | "medium" | "hard";

export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "fill_blank"
  | "short_answer"
  | "essay"
  | "calculation"
  | "case_analysis"
  | "reading_comprehension"
  | "cloze"
  | "translation"
  | "practical"
  | "composite";

export interface ExamQuestionRequirementDraft {
  id: string;
  question_type: QuestionType;
  question_count: string;
  score_per_question: string;
  total_score: string;
  preferred_difficulty: DifficultyLevel;
  knowledge_points_text: string;
  allow_ai_generation: boolean;
}

export interface ExamSectionDraft {
  id: string;
  section_name: string;
  section_order: string;
  section_score: string;
  instructions: string;
  question_requirements: ExamQuestionRequirementDraft[];
}

export interface ExamRequestDraft {
  paper_title: string;
  subject: string;
  school_stage: string;
  grade: string;
  exam_type: string;
  term: string;
  language: string;
  duration_minutes: string;
  total_score: string;
  target_question_count: string;
  knowledge_points_text: string;
  question_bank_ids_text: string;
  notes_to_generator: string;
  generation_mode: GenerationMode;
  sections: ExamSectionDraft[];
}

export interface ExamPaperValidatePayload {
  paper_title: string;
  subject: string;
  school_stage: string;
  grade: string;
  exam_type: string;
  term?: string;
  language: string;
  duration_minutes?: number;
  total_score: number;
  target_question_count?: number;
  knowledge_points: Array<{
    name: string;
    required: boolean;
  }>;
  sections: Array<{
    section_name: string;
    section_order?: number;
    section_score?: number;
    instructions?: string;
    question_requirements: Array<{
      question_type: QuestionType;
      question_count: number;
      score_per_question?: number;
      total_score?: number;
      preferred_difficulty?: DifficultyLevel;
      knowledge_points: string[];
      allow_ai_generation: boolean;
      constraints: string[];
    }>;
  }>;
  source_scope: {
    question_bank_ids: string[];
    syllabus_ids: string[];
    document_ids: string[];
    tags: string[];
    allowed_regions: string[];
    allowed_years: number[];
    exclude_question_ids: string[];
  };
  generation_policy: {
    mode: GenerationMode;
    allow_question_rewrite: boolean;
    allow_ai_generate_missing: boolean;
    deduplicate_questions: boolean;
    include_answers: boolean;
    include_explanations: boolean;
    max_candidate_questions_per_slot: number;
  };
  review_requirement: {
    enabled: boolean;
    require_answer_review: boolean;
    require_explanation_review: boolean;
    require_knowledge_point_review: boolean;
  };
  notes_to_generator?: string;
  output_formats: string[];
  metadata: Record<string, unknown>;
}

export interface ExamValidationIssue {
  level: "error" | "warning";
  code: string;
  message: string;
  path: string;
}

export interface ExamQualityIssue {
  level: "error" | "warning";
  code: string;
  message: string;
  path: string;
}

export interface ExamValidationSummary {
  paper_title: string;
  subject: string;
  school_stage: string;
  section_count: number;
  requested_total_score: number;
  computed_total_score: number | null;
  target_question_count: number | null;
  computed_question_count: number;
  knowledge_point_count: number;
  required_knowledge_points_without_mapping: string[];
  question_type_breakdown: Record<string, number>;
  generation_mode: string;
  output_formats: string[];
}

export interface ExamValidationResult {
  valid: boolean;
  schema_valid: boolean;
  business_valid: boolean;
  errors: ExamValidationIssue[];
  warnings: ExamValidationIssue[];
  summary: ExamValidationSummary | null;
  normalized_request: ExamPaperValidatePayload | null;
}

export interface ExamPreviewRequirementGroup {
  group_id: string;
  question_type: string;
  question_count: number;
  score_per_question: number | null;
  computed_total_score: number | null;
  difficulty: string | null;
  knowledge_points: string[];
  source_strategy: string;
  allow_ai_generation: boolean;
  slot_range: {
    start: number;
    end: number;
  };
}

export interface ExamPreviewSlot {
  slot_id: string;
  section_slot_index: number;
  global_slot_index: number;
  question_type: string;
  difficulty: string | null;
  score: number | null;
  knowledge_points: string[];
  source_strategy: string;
  allow_ai_generation: boolean;
  max_candidates: number;
}

export interface ExamPreviewSection {
  section_name: string;
  section_order: number;
  instructions?: string | null;
  requested_section_score: number | null;
  computed_section_score: number | null;
  question_slot_count: number;
  requirement_groups: ExamPreviewRequirementGroup[];
  question_slots: ExamPreviewSlot[];
}

export interface ExamPreviewData {
  paper_title: string;
  meta: {
    subject: string;
    school_stage: string;
    grade: string;
    exam_type: string;
    term?: string | null;
    language: string;
    duration_minutes?: number | null;
  };
  totals: {
    requested_total_score: number | null;
    estimated_total_score: number | null;
    requested_question_count: number | null;
    computed_question_count: number;
    section_count: number;
    question_bank_slot_count: number;
    ai_enabled_slot_count: number;
  };
  generation_policy: {
    mode: string;
    allow_question_rewrite: boolean;
    allow_ai_generate_missing: boolean;
    deduplicate_questions: boolean;
    include_answers: boolean;
    include_explanations: boolean;
    output_formats: string[];
  };
  source_scope: {
    question_bank_ids: string[];
    syllabus_ids: string[];
    document_ids: string[];
    tags: string[];
  };
  knowledge_points: Array<{
    name: string;
    required: boolean;
    target_question_count?: number | null;
    weight?: number | null;
  }>;
  sections: ExamPreviewSection[];
  generation_notes: string[];
  review_checklist: string[];
  validation_summary: ExamValidationSummary | null;
  warnings: ExamValidationIssue[];
}

export interface ExamPreviewResult {
  valid: boolean;
  validation: ExamValidationResult;
  preview: ExamPreviewData | null;
}

export interface ExamDraftOption {
  label: string;
  content: string;
  is_correct?: boolean | null;
}

export interface ExamDraftQuestionSnapshot {
  stem: string;
  options: ExamDraftOption[];
  reference_answer?: string | string[] | null;
  explanation?: string | null;
  knowledge_points: string[];
}

export interface ExamDraftQuestionRegenerationDiff {
  previous: ExamDraftQuestionSnapshot;
  current: ExamDraftQuestionSnapshot;
  comment?: string | null;
  regenerated_at: string;
}

export interface ExamDraftQuestion {
  question_id: string;
  slot_id: string;
  order: number;
  section_order: number;
  section_name: string;
  question_type: string;
  difficulty?: string | null;
  score?: number | null;
  source_strategy: string;
  draft_status: "template_preview" | "generated_preview" | "pending_regeneration";
  review_status: "pending_review" | "reviewed" | "rejected";
  knowledge_points: string[];
  stem: string;
  options: ExamDraftOption[];
  reference_answer?: string | string[] | null;
  explanation?: string | null;
  constraints: string[];
  quality_flags: string[];
  quality_issues: ExamQualityIssue[];
  review_comments: string[];
  review_history: Array<{
    reviewer: string;
    action: "approve" | "reject" | "request_regeneration";
    comment?: string | null;
    timestamp: string;
  }>;
  last_regeneration_diff?: ExamDraftQuestionRegenerationDiff | null;
}

export interface ExamDraftSection {
  section_name: string;
  section_order: number;
  instructions?: string | null;
  requested_section_score?: number | null;
  computed_section_score?: number | null;
  question_count: number;
  questions: ExamDraftQuestion[];
}

export interface ExamDraftData {
  paper_id: string;
  paper_title: string;
  generation_stage: "template_preview" | "generated_preview" | "mixed_preview";
  meta: {
    subject: string;
    school_stage: string;
    grade: string;
    exam_type: string;
    term?: string | null;
    language: string;
    duration_minutes?: number | null;
  };
  totals: {
    requested_total_score: number | null;
    estimated_total_score?: number | null;
    computed_question_count: number;
    requested_question_count?: number | null;
    section_count: number;
    question_bank_slot_count?: number;
    ai_enabled_slot_count?: number;
  };
  generation_policy: {
    mode: string;
    allow_question_rewrite: boolean;
    allow_ai_generate_missing: boolean;
    deduplicate_questions: boolean;
    include_answers: boolean;
    include_explanations: boolean;
    output_formats: string[];
  };
  source_scope: {
    question_bank_ids: string[];
    syllabus_ids: string[];
    document_ids: string[];
    tags: string[];
  };
  knowledge_points: Array<{
    name: string;
    required: boolean;
    target_question_count?: number | null;
    weight?: number | null;
  }>;
  sections: ExamDraftSection[];
  generation_notes: string[];
  review_checklist: string[];
  quality_summary: {
    total_questions: number;
    error_question_count: number;
    warning_question_count: number;
    total_issue_count: number;
    paper_level_issue_count: number;
    pending_regeneration_count: number;
    generated_question_count: number;
    template_question_count: number;
    computed_total_score?: number | null;
    score_fully_known: boolean;
    draft_status_breakdown: Record<string, number>;
  };
  review_summary: {
    pending_review_count: number;
    reviewed_count: number;
    rejected_count: number;
  };
  warnings: ExamValidationIssue[];
}

export interface ExamDraftResult {
  valid: boolean;
  validation: ExamValidationResult;
  paper: ExamDraftData | null;
}

export interface ExamQuestionReviewActionPayload {
  question_id: string;
  action: "approve" | "reject" | "request_regeneration";
  comment?: string;
  reviewer?: string;
}

export interface ExamPaperReviewRequestPayload {
  paper: ExamDraftData;
  actions: ExamQuestionReviewActionPayload[];
  reviewer?: string;
}

export interface ExamPaperReviewResult {
  valid: boolean;
  errors: ExamQualityIssue[];
  warnings: ExamQualityIssue[];
  applied_action_count: number;
  paper: ExamDraftData | null;
}
