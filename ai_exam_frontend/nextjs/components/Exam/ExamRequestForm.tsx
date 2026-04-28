import React from "react";
import {
  ExamRequestDraft,
  ExamQuestionRequirementDraft,
  ExamSectionDraft,
  QuestionType,
} from "@/types/exam";

interface ExamRequestFormProps {
  draft: ExamRequestDraft;
  setDraft: React.Dispatch<React.SetStateAction<ExamRequestDraft>>;
  onSubmit: () => void;
  disabled?: boolean;
}

const subjectOptions = [
  { value: "math", label: "数学" },
  { value: "chinese", label: "语文" },
  { value: "english", label: "英语" },
  { value: "physics", label: "物理" },
  { value: "chemistry", label: "化学" },
  { value: "biology", label: "生物" },
  { value: "history", label: "历史" },
  { value: "geography", label: "地理" },
  { value: "politics", label: "政治" },
];

const schoolStageOptions = [
  { value: "primary", label: "小学" },
  { value: "junior_high", label: "初中" },
  { value: "senior_high", label: "高中" },
  { value: "university", label: "大学" },
];

const generationModeOptions = [
  { value: "hybrid", label: "混合组卷" },
  { value: "question_bank_only", label: "仅题库抽题" },
  { value: "ai_generate_only", label: "仅 AI 出题" },
];

const questionTypeOptions: Array<{ value: QuestionType; label: string }> = [
  { value: "single_choice", label: "单选题" },
  { value: "multiple_choice", label: "多选题" },
  { value: "true_false", label: "判断题" },
  { value: "fill_blank", label: "填空题" },
  { value: "short_answer", label: "简答题" },
  { value: "essay", label: "作文 / 论述题" },
  { value: "calculation", label: "计算题" },
  { value: "case_analysis", label: "案例分析题" },
  { value: "reading_comprehension", label: "阅读理解题" },
  { value: "practical", label: "实践题" },
  { value: "composite", label: "综合题" },
];

const createQuestionRequirement = (): ExamQuestionRequirementDraft => ({
  id: `req-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  question_type: "single_choice",
  question_count: "10",
  score_per_question: "4",
  total_score: "",
  preferred_difficulty: "medium",
  knowledge_points_text: "",
  allow_ai_generation: true,
});

const createSection = (): ExamSectionDraft => ({
  id: `section-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  section_name: "选择题",
  section_order: "1",
  section_score: "",
  instructions: "",
  question_requirements: [createQuestionRequirement()],
});

const SectionCard: React.FC<{
  section: ExamSectionDraft;
  sectionIndex: number;
  disabled?: boolean;
  onSectionChange: (sectionId: string, field: keyof ExamSectionDraft, value: string) => void;
  onQuestionRequirementChange: (
    sectionId: string,
    requirementId: string,
    field: keyof ExamQuestionRequirementDraft,
    value: string | boolean
  ) => void;
  onAddRequirement: (sectionId: string) => void;
  onRemoveRequirement: (sectionId: string, requirementId: string) => void;
  onRemoveSection: (sectionId: string) => void;
}> = ({
  section,
  sectionIndex,
  disabled = false,
  onSectionChange,
  onQuestionRequirementChange,
  onAddRequirement,
  onRemoveRequirement,
  onRemoveSection,
}) => {
  return (
    <div className="apple-panel rounded-[26px] border border-white/8 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-white/34">
            Section {sectionIndex + 1}
          </div>
          <div className="text-sm font-medium text-white/84">大题结构</div>
        </div>
        <button
          type="button"
          onClick={() => onRemoveSection(section.id)}
          className="apple-button-ghost rounded-full px-3 py-2 text-xs text-white/58"
          disabled={disabled}
        >
          删除大题
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <LabeledInput
          label="大题名称"
          value={section.section_name}
          onChange={(value) => onSectionChange(section.id, "section_name", value)}
          placeholder="如：选择题、解答题"
          disabled={disabled}
        />
        <LabeledInput
          label="排序"
          type="number"
          value={section.section_order}
          onChange={(value) => onSectionChange(section.id, "section_order", value)}
          placeholder="1"
          disabled={disabled}
        />
        <LabeledInput
          label="大题总分"
          type="number"
          value={section.section_score}
          onChange={(value) => onSectionChange(section.id, "section_score", value)}
          placeholder="可留空"
          disabled={disabled}
        />
      </div>

      <div className="mt-4">
        <LabeledTextarea
          label="作答说明"
          value={section.instructions}
          onChange={(value) => onSectionChange(section.id, "instructions", value)}
          placeholder="如：本大题共 10 小题，每题只有 1 个正确答案。"
          disabled={disabled}
          rows={2}
        />
      </div>

      <div className="mt-5 space-y-4">
        {section.question_requirements.map((requirement, requirementIndex) => (
          <div
            key={requirement.id}
            className="rounded-[22px] border border-white/8 bg-white/[0.02] p-4"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="text-sm font-medium text-white/82">
                题型要求 {requirementIndex + 1}
              </div>
              <button
                type="button"
                onClick={() => onRemoveRequirement(section.id, requirement.id)}
                className="apple-button-ghost rounded-full px-3 py-1.5 text-xs text-white/58"
                disabled={disabled || section.question_requirements.length === 1}
              >
                删除题型
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <LabeledSelect
                label="题型"
                value={requirement.question_type}
                onChange={(value) =>
                  onQuestionRequirementChange(section.id, requirement.id, "question_type", value)
                }
                options={questionTypeOptions}
                disabled={disabled}
              />
              <LabeledInput
                label="题量"
                type="number"
                value={requirement.question_count}
                onChange={(value) =>
                  onQuestionRequirementChange(section.id, requirement.id, "question_count", value)
                }
                disabled={disabled}
              />
              <LabeledInput
                label="每题分值"
                type="number"
                value={requirement.score_per_question}
                onChange={(value) =>
                  onQuestionRequirementChange(section.id, requirement.id, "score_per_question", value)
                }
                placeholder="可留空"
                disabled={disabled}
              />
              <LabeledInput
                label="题型总分"
                type="number"
                value={requirement.total_score}
                onChange={(value) =>
                  onQuestionRequirementChange(section.id, requirement.id, "total_score", value)
                }
                placeholder="可留空"
                disabled={disabled}
              />
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <LabeledSelect
                label="偏好难度"
                value={requirement.preferred_difficulty}
                onChange={(value) =>
                  onQuestionRequirementChange(
                    section.id,
                    requirement.id,
                    "preferred_difficulty",
                    value
                  )
                }
                options={[
                  { value: "easy", label: "简单" },
                  { value: "medium", label: "中等" },
                  { value: "hard", label: "困难" },
                ]}
                disabled={disabled}
              />

              <label className="flex items-end gap-3 rounded-[18px] border border-white/8 px-4 py-3 text-sm text-white/72">
                <input
                  type="checkbox"
                  checked={requirement.allow_ai_generation}
                  onChange={(event) =>
                    onQuestionRequirementChange(
                      section.id,
                      requirement.id,
                      "allow_ai_generation",
                      event.target.checked
                    )
                  }
                  disabled={disabled}
                  className="mt-0.5 h-4 w-4 rounded border-white/20 bg-transparent"
                />
                <div>
                  <div className="font-medium text-white/86">题库不足时允许 AI 补题</div>
                  <div className="mt-1 text-xs text-white/44">
                    对纯题库模式，这个开关会在后端被提示为无效配置。
                  </div>
                </div>
              </label>
            </div>

            <div className="mt-4">
              <LabeledTextarea
                label="该题型覆盖的知识点"
                value={requirement.knowledge_points_text}
                onChange={(value) =>
                  onQuestionRequirementChange(
                    section.id,
                    requirement.id,
                    "knowledge_points_text",
                    value
                  )
                }
                placeholder="多个知识点用逗号或换行分隔"
                disabled={disabled}
                rows={2}
              />
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => onAddRequirement(section.id)}
        className="apple-button-secondary mt-4 rounded-full px-4 py-2 text-sm"
        disabled={disabled}
      >
        添加题型要求
      </button>
    </div>
  );
};

const LabeledInput: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
}> = ({ label, value, onChange, placeholder, type = "text", disabled = false }) => (
  <label className="block">
    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-white/36">{label}</div>
    <input
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className="w-full rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none placeholder:text-white/24"
    />
  </label>
);

const LabeledTextarea: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}> = ({ label, value, onChange, placeholder, rows = 3, disabled = false }) => (
  <label className="block">
    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-white/36">{label}</div>
    <textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      rows={rows}
      disabled={disabled}
      className="w-full rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-white/24"
    />
  </label>
);

const LabeledSelect: React.FC<{
  label: string;
  value: string;
  onChange: (value: any) => void;
  options: Array<{ value: string; label: string }>;
  disabled?: boolean;
}> = ({ label, value, onChange, options, disabled = false }) => (
  <label className="block">
    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-white/36">{label}</div>
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="w-full rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value} className="bg-[#111214] text-white">
          {option.label}
        </option>
      ))}
    </select>
  </label>
);

export default function ExamRequestForm({
  draft,
  setDraft,
  onSubmit,
  disabled = false,
}: ExamRequestFormProps) {
  const updateField = <K extends keyof ExamRequestDraft>(field: K, value: ExamRequestDraft[K]) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const updateSection = (sectionId: string, field: keyof ExamSectionDraft, value: string) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((section) =>
        section.id === sectionId ? { ...section, [field]: value } : section
      ),
    }));
  };

  const updateQuestionRequirement = (
    sectionId: string,
    requirementId: string,
    field: keyof ExamQuestionRequirementDraft,
    value: string | boolean
  ) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((section) => {
        if (section.id !== sectionId) return section;
        return {
          ...section,
          question_requirements: section.question_requirements.map((requirement) =>
            requirement.id === requirementId ? { ...requirement, [field]: value } : requirement
          ),
        };
      }),
    }));
  };

  const addSection = () => {
    setDraft((prev) => ({ ...prev, sections: [...prev.sections, createSection()] }));
  };

  const removeSection = (sectionId: string) => {
    setDraft((prev) => ({
      ...prev,
      sections:
        prev.sections.length === 1
          ? prev.sections
          : prev.sections.filter((section) => section.id !== sectionId),
    }));
  };

  const addRequirement = (sectionId: string) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((section) =>
        section.id === sectionId
          ? {
              ...section,
              question_requirements: [...section.question_requirements, createQuestionRequirement()],
            }
          : section
      ),
    }));
  };

  const removeRequirement = (sectionId: string, requirementId: string) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((section) => {
        if (section.id !== sectionId || section.question_requirements.length === 1) {
          return section;
        }
        return {
          ...section,
          question_requirements: section.question_requirements.filter(
            (requirement) => requirement.id !== requirementId
          ),
        };
      }),
    }));
  };

  return (
    <div className="space-y-6">
      <div className="apple-panel-strong rounded-[30px] border border-white/8 p-5 sm:p-6">
        <div className="mb-5">
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            AI 组卷请求
          </div>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-white">
            先把组卷约束说清楚，再让后端校验请求结构。
          </h2>
          <p className="mt-3 max-w-[760px] text-sm leading-6 text-white/52">
            当前这一版前端先对接后端验证接口，不直接生成试卷。目标是把组卷输入结构固定下来，
            让后面的题库抽题、AI 补题和人工审核都建立在同一份请求模型上。
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <LabeledInput
            label="试卷标题"
            value={draft.paper_title}
            onChange={(value) => updateField("paper_title", value)}
            placeholder="如：九年级数学单元测验"
            disabled={disabled}
          />
          <LabeledSelect
            label="学科"
            value={draft.subject}
            onChange={(value) => updateField("subject", value)}
            options={subjectOptions}
            disabled={disabled}
          />
          <LabeledSelect
            label="学段"
            value={draft.school_stage}
            onChange={(value) => updateField("school_stage", value)}
            options={schoolStageOptions}
            disabled={disabled}
          />
          <LabeledInput
            label="年级"
            value={draft.grade}
            onChange={(value) => updateField("grade", value)}
            placeholder="如：grade_9"
            disabled={disabled}
          />
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <LabeledInput
            label="考试类型"
            value={draft.exam_type}
            onChange={(value) => updateField("exam_type", value)}
            placeholder="如：unit_test / midterm"
            disabled={disabled}
          />
          <LabeledInput
            label="学期"
            value={draft.term}
            onChange={(value) => updateField("term", value)}
            placeholder="如：spring"
            disabled={disabled}
          />
          <LabeledInput
            label="时长（分钟）"
            type="number"
            value={draft.duration_minutes}
            onChange={(value) => updateField("duration_minutes", value)}
            disabled={disabled}
          />
          <LabeledInput
            label="总分"
            type="number"
            value={draft.total_score}
            onChange={(value) => updateField("total_score", value)}
            disabled={disabled}
          />
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <LabeledInput
            label="目标题量"
            type="number"
            value={draft.target_question_count}
            onChange={(value) => updateField("target_question_count", value)}
            placeholder="可留空"
            disabled={disabled}
          />
          <LabeledInput
            label="输出语言"
            value={draft.language}
            onChange={(value) => updateField("language", value)}
            disabled={disabled}
          />
          <LabeledSelect
            label="组卷模式"
            value={draft.generation_mode}
            onChange={(value) => updateField("generation_mode", value)}
            options={generationModeOptions}
            disabled={disabled}
          />
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <LabeledTextarea
            label="全卷知识点"
            value={draft.knowledge_points_text}
            onChange={(value) => updateField("knowledge_points_text", value)}
            placeholder="多个知识点用逗号或换行分隔"
            disabled={disabled}
          />
          <LabeledTextarea
            label="题库范围"
            value={draft.question_bank_ids_text}
            onChange={(value) => updateField("question_bank_ids_text", value)}
            placeholder="多个题库 ID 用逗号或换行分隔"
            disabled={disabled}
          />
        </div>

        <div className="mt-4">
          <LabeledTextarea
            label="补充要求"
            value={draft.notes_to_generator}
            onChange={(value) => updateField("notes_to_generator", value)}
            placeholder="如：整体难度前易后难，避免竞赛题，解析尽量简洁。"
            rows={3}
            disabled={disabled}
          />
        </div>
      </div>

      <div className="space-y-4">
        {draft.sections.map((section, sectionIndex) => (
          <SectionCard
            key={section.id}
            section={section}
            sectionIndex={sectionIndex}
            disabled={disabled}
            onSectionChange={updateSection}
            onQuestionRequirementChange={updateQuestionRequirement}
            onAddRequirement={addRequirement}
            onRemoveRequirement={removeRequirement}
            onRemoveSection={removeSection}
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[26px] border border-white/8 bg-white/[0.02] px-5 py-4">
        <button
          type="button"
          onClick={addSection}
          className="apple-button-secondary rounded-full px-5 py-3 text-sm font-medium"
          disabled={disabled}
        >
          添加大题
        </button>

        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled}
          className="apple-button-primary rounded-full px-6 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? "正在校验请求..." : "提交后端校验"}
        </button>
      </div>
    </div>
  );
}
