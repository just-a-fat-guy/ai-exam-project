"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWebSocket } from '@/hooks/useWebSocket';
import { useResearchHistoryContext } from '@/hooks/ResearchHistoryContext';
import { useScrollHandler } from '@/hooks/useScrollHandler';
import { startLanggraphResearch } from '../components/Langgraph/Langgraph';
import findDifferences from '../helpers/findDifferences';
import { Data, ChatBoxSettings, QuestionData, ChatMessage, ChatData } from '../types/data';
import {
  ExamDraftData,
  ExamDraftResult,
  ExamPaperReviewResult,
  ExamPaperValidatePayload,
  ExamRequestDraft,
  ExamValidationResult,
} from '../types/exam';
import { preprocessOrderedData } from '../utils/dataProcessing';
import { toast } from "react-hot-toast";
import { v4 as uuidv4 } from 'uuid';

import Hero from "@/components/Hero";
import ResearchPageLayout from "@/components/layouts/ResearchPageLayout";
import CopilotLayout from "@/components/layouts/CopilotLayout";
import ResearchContent from "@/components/research/ResearchContent";
import CopilotResearchContent from "@/components/research/CopilotResearchContent";
import HumanFeedback from "@/components/HumanFeedback";
import ResearchSidebar from "@/components/ResearchSidebar";
import { getAppropriateLayout } from "@/utils/getLayout";

// Import the mobile components
import MobileHomeScreen from "@/components/mobile/MobileHomeScreen";
import MobileResearchContent from "@/components/mobile/MobileResearchContent";

const createInitialExamDraft = (): ExamRequestDraft => ({
  paper_title: "2026年春季九年级数学单元测验",
  subject: "math",
  school_stage: "junior_high",
  grade: "grade_9",
  exam_type: "unit_test",
  term: "spring",
  language: "zh-CN",
  duration_minutes: "90",
  total_score: "120",
  target_question_count: "22",
  knowledge_points_text: "一元二次方程\n二次函数",
  question_bank_ids_text: "bank_math_junior",
  notes_to_generator: "整体难度前易后难，避免超纲内容。",
  generation_mode: "hybrid",
  sections: [
    {
      id: "section-default-1",
      section_name: "选择题",
      section_order: "1",
      section_score: "40",
      instructions: "本大题共 10 小题，每题只有 1 个正确答案。",
      question_requirements: [
        {
          id: "req-default-1",
          question_type: "single_choice",
          question_count: "10",
          score_per_question: "4",
          total_score: "",
          preferred_difficulty: "easy",
          knowledge_points_text: "一元二次方程, 二次函数",
          allow_ai_generation: false,
        },
      ],
    },
    {
      id: "section-default-2",
      section_name: "解答题",
      section_order: "2",
      section_score: "80",
      instructions: "要求写出必要的推理和计算过程。",
      question_requirements: [
        {
          id: "req-default-2",
          question_type: "calculation",
          question_count: "4",
          score_per_question: "",
          total_score: "32",
          preferred_difficulty: "medium",
          knowledge_points_text: "一元二次方程",
          allow_ai_generation: true,
        },
        {
          id: "req-default-3",
          question_type: "case_analysis",
          question_count: "2",
          score_per_question: "",
          total_score: "48",
          preferred_difficulty: "hard",
          knowledge_points_text: "二次函数",
          allow_ai_generation: true,
        },
      ],
    },
  ],
});

const parseTextList = (value: string) =>
  value
    .split(/[\n,，;]/)
    .map((item) => item.trim())
    .filter(Boolean);

const toNumberOrUndefined = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const buildExamPayload = (
  draft: ExamRequestDraft,
  settings: ChatBoxSettings
): ExamPaperValidatePayload => ({
  paper_title: draft.paper_title.trim(),
  subject: draft.subject,
  school_stage: draft.school_stage,
  grade: draft.grade.trim(),
  exam_type: draft.exam_type.trim(),
  term: draft.term.trim() || undefined,
  language: draft.language.trim() || "zh-CN",
  duration_minutes: toNumberOrUndefined(draft.duration_minutes),
  total_score: Number(draft.total_score || 0),
  target_question_count: toNumberOrUndefined(draft.target_question_count),
  knowledge_points: parseTextList(draft.knowledge_points_text).map((name) => ({
    name,
    required: true,
  })),
  sections: draft.sections.map((section) => ({
    section_name: section.section_name.trim(),
    section_order: toNumberOrUndefined(section.section_order),
    section_score: toNumberOrUndefined(section.section_score),
    instructions: section.instructions.trim() || undefined,
    question_requirements: section.question_requirements.map((requirement) => ({
      question_type: requirement.question_type,
      question_count: Number(requirement.question_count || 0),
      score_per_question: toNumberOrUndefined(requirement.score_per_question),
      total_score: toNumberOrUndefined(requirement.total_score),
      preferred_difficulty: requirement.preferred_difficulty,
      knowledge_points: parseTextList(requirement.knowledge_points_text),
      allow_ai_generation: requirement.allow_ai_generation,
      constraints: [],
    })),
  })),
  source_scope: {
    question_bank_ids: parseTextList(draft.question_bank_ids_text),
    syllabus_ids: [],
    document_ids: [],
    tags: [],
    allowed_regions: [],
    allowed_years: [],
    exclude_question_ids: [],
  },
  generation_policy: {
    mode: (draft.generation_mode || settings.generation_mode || "hybrid") as ExamPaperValidatePayload["generation_policy"]["mode"],
    allow_question_rewrite: false,
    allow_ai_generate_missing: true,
    deduplicate_questions: true,
    include_answers: settings.include_answers ?? true,
    include_explanations: settings.include_explanations ?? true,
    max_candidate_questions_per_slot: 5,
  },
  review_requirement: {
    enabled: true,
    require_answer_review: true,
    require_explanation_review: true,
    require_knowledge_point_review: false,
  },
  notes_to_generator: draft.notes_to_generator.trim() || undefined,
  output_formats: settings.output_formats?.length ? settings.output_formats : ["json", "docx"],
  metadata: {
    source: "frontend_exam_request_form",
  },
});

const buildExamTaskSummary = (draft: ExamRequestDraft) =>
  [
    draft.paper_title.trim(),
    subjectLabelMap[draft.subject] || draft.subject,
    draft.grade.trim(),
    draft.exam_type.trim(),
  ]
    .filter(Boolean)
    .join(" | ");

const buildValidationMarkdown = (
  result: ExamValidationResult,
  payload: ExamPaperValidatePayload
) => {
  const lines: string[] = [];
  const summary = result.summary;

  lines.push(`# 组卷请求校验结果`);
  lines.push("");
  lines.push(`- 总体结论：${result.valid ? "通过" : "未通过"}`);
  lines.push(`- Schema 校验：${result.schema_valid ? "通过" : "未通过"}`);
  lines.push(`- 业务规则校验：${result.business_valid ? "通过" : "未通过"}`);
  lines.push("");

  if (summary) {
    lines.push("## 请求摘要");
    lines.push("");
    lines.push(`- 试卷标题：${summary.paper_title}`);
    lines.push(`- 学科 / 学段：${summary.subject} / ${summary.school_stage}`);
    lines.push(`- 大题数量：${summary.section_count}`);
    lines.push(`- 目标总分：${summary.requested_total_score}`);
    lines.push(`- 推导总分：${summary.computed_total_score ?? "无法完整推导"}`);
    lines.push(`- 目标题量：${summary.target_question_count ?? "未设置"}`);
    lines.push(`- 推导题量：${summary.computed_question_count}`);
    lines.push(`- 组卷模式：${summary.generation_mode}`);
    lines.push(`- 输出格式：${summary.output_formats.join(", ") || "未设置"}`);
    lines.push("");

    if (Object.keys(summary.question_type_breakdown || {}).length > 0) {
      lines.push("## 题型拆分");
      lines.push("");
      Object.entries(summary.question_type_breakdown).forEach(([questionType, count]) => {
        lines.push(`- ${questionType}：${count} 题`);
      });
      lines.push("");
    }
  }

  if (result.errors.length > 0) {
    lines.push("## 错误");
    lines.push("");
    result.errors.forEach((issue) => {
      lines.push(`- [${issue.path}] ${issue.message}`);
    });
    lines.push("");
  }

  if (result.warnings.length > 0) {
    lines.push("## 警告");
    lines.push("");
    result.warnings.forEach((issue) => {
      lines.push(`- [${issue.path}] ${issue.message}`);
    });
    lines.push("");
  }

  lines.push("## 已提交的核心约束");
  lines.push("");
  lines.push(`- 全卷知识点：${payload.knowledge_points.map((item) => item.name).join("、") || "未填写"}`);
  lines.push(`- 题库范围：${payload.source_scope.question_bank_ids.join("、") || "未填写"}`);
  lines.push(`- 备注：${payload.notes_to_generator || "无"}`);

  return lines.join("\n");
};

const questionTypeLabelMap: Record<string, string> = {
  single_choice: "单选题",
  multiple_choice: "多选题",
  true_false: "判断题",
  fill_blank: "填空题",
  short_answer: "简答题",
  essay: "作文 / 论述题",
  calculation: "计算题",
  case_analysis: "案例分析题",
  reading_comprehension: "阅读理解题",
  cloze: "完形填空",
  translation: "翻译题",
  practical: "实践题",
  composite: "综合题",
};

const difficultyLabelMap: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
};

const sourceStrategyLabelMap: Record<string, string> = {
  question_bank_only: "仅题库",
  ai_generate_only: "仅 AI 生成",
  question_bank_first_then_ai: "题库优先，不足时 AI 补题",
};

const buildDraftMarkdownFromPaper = (
  paper: ExamDraftData | null,
  validation: ExamValidationResult | null,
  payload?: ExamPaperValidatePayload
) => {
  if (!paper) {
    return validation && payload ? buildValidationMarkdown(validation, payload) : "# 试卷草案为空";
  }

  const lines: string[] = [];

  lines.push("# 试卷草案预览");
  lines.push("");
  lines.push(`- 草案 ID：${paper.paper_id}`);
  lines.push(`- 试卷标题：${paper.paper_title}`);
  lines.push(`- 学科 / 学段：${subjectLabelMap[paper.meta.subject] || paper.meta.subject} / ${paper.meta.school_stage}`);
  lines.push(`- 年级 / 考试类型：${paper.meta.grade} / ${paper.meta.exam_type}`);
  lines.push(`- 语言 / 时长：${paper.meta.language} / ${paper.meta.duration_minutes ?? "未设置"} 分钟`);
  lines.push(`- 生成阶段：${paper.generation_stage}`);
  lines.push("");

  lines.push("## 整体摘要");
  lines.push("");
  lines.push(`- 大题数量：${paper.totals.section_count}`);
  lines.push(`- 请求总分：${paper.totals.requested_total_score ?? "未设置"}`);
  lines.push(`- 预估总分：${paper.totals.estimated_total_score ?? "无法完整推导"}`);
  lines.push(`- 请求题量：${paper.totals.requested_question_count ?? "未设置"}`);
  lines.push(`- 当前草案题量：${paper.totals.computed_question_count}`);
  if (typeof paper.totals.question_bank_slot_count === "number") {
    lines.push(`- 题库相关题位：${paper.totals.question_bank_slot_count}`);
  }
  if (typeof paper.totals.ai_enabled_slot_count === "number") {
    lines.push(`- 允许 AI 参与题位：${paper.totals.ai_enabled_slot_count}`);
  }
  lines.push("");

  lines.push("## 组卷策略");
  lines.push("");
  lines.push(`- 模式：${sourceStrategyLabelMap[paper.generation_policy.mode] || paper.generation_policy.mode}`);
  lines.push(`- 输出格式：${paper.generation_policy.output_formats.join(", ") || "未设置"}`);
  lines.push(`- 包含答案：${paper.generation_policy.include_answers ? "是" : "否"}`);
  lines.push(`- 包含解析：${paper.generation_policy.include_explanations ? "是" : "否"}`);
  lines.push(`- 题目去重：${paper.generation_policy.deduplicate_questions ? "开启" : "关闭"}`);
  lines.push("");

  if (paper.quality_summary) {
    lines.push("## 质量摘要");
    lines.push("");
    lines.push(`- 总题数：${paper.quality_summary.total_questions}`);
    lines.push(`- 存在错误的题目数：${paper.quality_summary.error_question_count}`);
    lines.push(`- 存在警告的题目数：${paper.quality_summary.warning_question_count}`);
    lines.push(`- 总问题数：${paper.quality_summary.total_issue_count}`);
    lines.push(`- 待重生成题目数：${paper.quality_summary.pending_regeneration_count}`);
    lines.push(`- AI 已生成题目数：${paper.quality_summary.generated_question_count}`);
    lines.push(`- 模板 / 回退题目数：${paper.quality_summary.template_question_count}`);
    lines.push(`- 审核中题目数：${paper.review_summary?.pending_review_count ?? 0}`);
    lines.push(`- 已通过审核题目数：${paper.review_summary?.reviewed_count ?? 0}`);
    lines.push(`- 已驳回题目数：${paper.review_summary?.rejected_count ?? 0}`);
    lines.push("");
  }

  if (paper.source_scope.question_bank_ids.length > 0) {
    lines.push("## 题库范围");
    lines.push("");
    paper.source_scope.question_bank_ids.forEach((id) => {
      lines.push(`- ${id}`);
    });
    lines.push("");
  }

  if (paper.knowledge_points.length > 0) {
    lines.push("## 全卷知识点");
    lines.push("");
    paper.knowledge_points.forEach((point) => {
      const targetCount = point.target_question_count ? `，目标题量 ${point.target_question_count}` : "";
      lines.push(`- ${point.name}${point.required ? "（必考）" : ""}${targetCount}`);
    });
    lines.push("");
  }

  lines.push("## 试卷草案");
  lines.push("");
  paper.sections.forEach((section, sectionIndex) => {
    lines.push(`### ${sectionIndex + 1}. ${section.section_name}`);
    lines.push("");
    lines.push(`- 排序：${section.section_order}`);
    lines.push(`- 题目数：${section.question_count}`);
    lines.push(`- 请求分值：${section.requested_section_score ?? "未设置"}`);
    lines.push(`- 当前草案分值：${section.computed_section_score ?? "无法完整推导"}`);
    if (section.instructions) {
      lines.push(`- 作答说明：${section.instructions}`);
    }
    lines.push("");

    section.questions.forEach((question, questionIndex) => {
      lines.push(
        `#### ${sectionIndex + 1}.${questionIndex + 1} ` +
        `${questionTypeLabelMap[question.question_type] || question.question_type}`
      );
      lines.push("");
      lines.push(
        `- 题号：${question.question_id}，题位：${question.slot_id}，分值：${question.score ?? "未设置"}，` +
        `难度 ${question.difficulty ? difficultyLabelMap[question.difficulty] || question.difficulty : "未指定"}，` +
        `来源策略 ${sourceStrategyLabelMap[question.source_strategy] || question.source_strategy}`
      );
      lines.push(`- 草案状态：${question.draft_status}，审核状态：${question.review_status}`);
      if (question.knowledge_points.length > 0) {
        lines.push(`- 覆盖知识点：${question.knowledge_points.join("、")}`);
      }
      lines.push(`- 题干：${question.stem}`);
      if (question.options.length > 0) {
        lines.push("- 选项：");
        question.options.forEach((option) => {
          lines.push(
            `  - ${option.label}. ${option.content}` +
            (option.is_correct === true ? " [参考正确]" : "")
          );
        });
      }
      if (question.reference_answer) {
        lines.push(
          `- 参考答案：${Array.isArray(question.reference_answer) ? question.reference_answer.join("、") : question.reference_answer}`
        );
      }
      if (question.explanation) {
        lines.push(`- 参考解析：${question.explanation}`);
      }
      if (question.quality_flags.length > 0) {
        lines.push(`- 质量标记：${question.quality_flags.join("、")}`);
      }
      if (question.quality_issues.length > 0) {
        lines.push("- 质量问题：");
        question.quality_issues.forEach((issue) => {
          lines.push(`  - [${issue.level}] ${issue.message}`);
        });
      }
      if (question.review_comments.length > 0) {
        lines.push("- 审核备注：");
        question.review_comments.forEach((comment) => {
          lines.push(`  - ${comment}`);
        });
      }
      lines.push("");
    });
  });

  if (paper.generation_notes.length > 0) {
    lines.push("## 生成说明");
    lines.push("");
    paper.generation_notes.forEach((note) => {
      lines.push(`- ${note}`);
    });
    lines.push("");
  }

  if (paper.review_checklist.length > 0) {
    lines.push("## 人工审核清单");
    lines.push("");
    paper.review_checklist.forEach((item) => {
      lines.push(`- ${item}`);
    });
    lines.push("");
  }

  if (paper.warnings.length > 0 || (validation?.warnings?.length || 0) > 0) {
    lines.push("## 仍需注意的警告");
    lines.push("");
    [...paper.warnings, ...(validation?.warnings || [])].forEach((issue) => {
      lines.push(`- [${issue.path}] ${issue.message}`);
    });
    lines.push("");
  }

  return lines.join("\n");
};

const buildDraftMarkdown = (
  draftResult: ExamDraftResult,
  payload: ExamPaperValidatePayload
) => buildDraftMarkdownFromPaper(draftResult.paper, draftResult.validation, payload);

const subjectLabelMap: Record<string, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  physics: "物理",
  chemistry: "化学",
  biology: "生物",
  history: "历史",
  geography: "地理",
  politics: "政治",
};

export default function Home() {
  const router = useRouter();
  const [promptValue, setPromptValue] = useState("");
  const [chatPromptValue, setChatPromptValue] = useState("");
  const [showResult, setShowResult] = useState(false);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [isInChatMode, setIsInChatMode] = useState(false);
  const [examDraft, setExamDraft] = useState<ExamRequestDraft>(createInitialExamDraft);
  const [currentExamPaper, setCurrentExamPaper] = useState<ExamDraftData | null>(null);
  const [currentExamValidation, setCurrentExamValidation] = useState<ExamValidationResult | null>(null);
  const [reviewingQuestionIds, setReviewingQuestionIds] = useState<string[]>([]);
  const [chatBoxSettings, setChatBoxSettings] = useState<ChatBoxSettings>(() => {
    // Default settings
    const defaultSettings = {
      workflow_mode: "exam",
      report_type: "research_report",
      report_source: "web",
      tone: "Objective",
      domains: [],
      defaultReportType: "research_report",
      layoutType: 'research',
      mcp_enabled: false,
      mcp_configs: [],
      mcp_strategy: "fast",
      generation_mode: "hybrid",
      include_answers: true,
      include_explanations: true,
      output_formats: ["json", "docx"],
    };

    // Try to load all settings from localStorage
    if (typeof window !== 'undefined') {
      const savedSettings = localStorage.getItem('chatBoxSettings');
      if (savedSettings) {
        try {
          const parsedSettings = JSON.parse(savedSettings);
          return {
            ...defaultSettings,
            ...parsedSettings, // Override defaults with saved settings
          };
        } catch (e) {
          console.error('Error parsing saved settings:', e);
        }
      }
    }
    return defaultSettings;
  });
  const [question, setQuestion] = useState("");
  const [orderedData, setOrderedData] = useState<Data[]>([]);
  const [showHumanFeedback, setShowHumanFeedback] = useState(false);
  const [questionForHuman, setQuestionForHuman] = useState<true | false>(false);
  const [allLogs, setAllLogs] = useState<any[]>([]);
  const [isStopped, setIsStopped] = useState(false);
  const mainContentRef = useRef<HTMLDivElement>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [currentResearchId, setCurrentResearchId] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [isProcessingChat, setIsProcessingChat] = useState(false);
  const isExamWorkflow = (chatBoxSettings.workflow_mode || "exam") === "exam";

  // Use our custom scroll handler
  const { showScrollButton, scrollToBottom } = useScrollHandler(mainContentRef);

  // Check if we're on mobile
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    // Initial check
    checkIfMobile();
    
    // Add event listener for window resize
    window.addEventListener('resize', checkIfMobile);
    
    // Cleanup
    return () => window.removeEventListener('resize', checkIfMobile);
  }, []);

  const { 
    history, 
    saveResearch, 
    updateResearch,
    getResearchById, 
    deleteResearch,
    addChatMessage,
    getChatMessages
  } = useResearchHistoryContext();

  // Only initialize the WebSocket hook reference, don't connect automatically
  const websocketRef = useRef(useWebSocket(
    setOrderedData,
    setAnswer,
    setLoading,
    setShowHumanFeedback,
    setQuestionForHuman
  ));
  
  // Use the reference to access websocket functions
  const { socket, initializeWebSocket } = websocketRef.current;

  const handleFeedbackSubmit = (feedback: string | null) => {
    if (socket) {
      socket.send(JSON.stringify({ type: 'human_feedback', content: feedback }));
    }
    setShowHumanFeedback(false);
  };

  const handleValidateExamRequest = async () => {
    const payload = buildExamPayload(examDraft, chatBoxSettings);
    const taskSummary = buildExamTaskSummary(examDraft);

    setIsInChatMode(false);
    setShowResult(true);
    setLoading(true);
    setQuestion(taskSummary);
    setAnswer("");
    setAllLogs([]);
    setCurrentResearchId(null);
    setCurrentExamPaper(null);
    setCurrentExamValidation(null);
    setReviewingQuestionIds([]);
    setOrderedData([{ type: "question", content: taskSummary } as QuestionData]);
    setChatBoxSettings((prev) => ({
      ...prev,
      workflow_mode: "exam",
      layoutType: "research",
    }));

    try {
      const response = await fetch("/api/exam-papers/validate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Failed to validate exam request: ${response.status}`);
      }

      const result: ExamValidationResult = await response.json();
      if (!result.valid) {
        setCurrentExamValidation(result);
        const markdown = buildValidationMarkdown(result, payload);
        setAnswer(markdown);
        setOrderedData([
          { type: "question", content: taskSummary } as QuestionData,
          { type: "report_complete", output: markdown } as Data,
        ]);
        toast.error("组卷请求未通过校验");
        return;
      }

      const previewResponse = await fetch("/api/exam-papers/generate-preview-paper", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!previewResponse.ok) {
        throw new Error(`Failed to build exam draft: ${previewResponse.status}`);
      }

      const previewResult: ExamDraftResult = await previewResponse.json();
      if (!previewResult.valid || !previewResult.paper) {
        setCurrentExamValidation(previewResult.validation);
        const markdown =
          buildValidationMarkdown(previewResult.validation, payload) +
          "\n\n## 草案状态\n\n组卷请求虽然通过了基础校验，但题目级试卷草案尚未生成成功。";
        setAnswer(markdown);
        setOrderedData([
          { type: "question", content: taskSummary } as QuestionData,
          { type: "report_complete", output: markdown } as Data,
        ]);
        toast.error("校验通过，但试卷草案生成失败");
        return;
      }

      setCurrentExamPaper(previewResult.paper);
      setCurrentExamValidation(previewResult.validation);
      const markdown = buildDraftMarkdown(previewResult, payload);
      setAnswer(markdown);
      setOrderedData([
        { type: "question", content: taskSummary } as QuestionData,
        { type: "report_complete", output: markdown } as Data,
      ]);

      toast.success("题目级试卷草案已生成");
    } catch (error) {
      console.error("Exam request validation error:", error);
      const fallbackMarkdown = [
        "# 试卷草案生成失败",
        "",
        "后端校验或题目级草案接口调用失败，当前无法生成这份组卷请求的试卷草案。",
        "",
        "请优先检查：",
        "- 后端服务是否已启动",
        "- `/api/exam-papers/validate` 是否可访问",
        "- `/api/exam-papers/generate-preview-paper` 是否可访问",
        "- 当前请求字段是否被前端正确序列化",
      ].join("\n");

      setAnswer(fallbackMarkdown);
      setOrderedData([
        { type: "question", content: taskSummary } as QuestionData,
        { type: "report_complete", output: fallbackMarkdown } as Data,
      ]);
      toast.error("试卷草案生成失败");
    } finally {
      setLoading(false);
    }
  };

  const handleReviewExamQuestion = async (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration",
    comment?: string
  ) => {
    if (!currentExamPaper) {
      toast.error("当前没有可审核的试卷草案");
      return false;
    }

    if ((action === "reject" || action === "request_regeneration") && !comment?.trim()) {
      toast.error("驳回或重生成时需要填写审核原因");
      return false;
    }

    setReviewingQuestionIds((prev) => [...prev, questionId]);

    try {
      const response = await fetch("/api/exam-papers/review-actions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          paper: currentExamPaper,
          reviewer: "frontend_teacher",
          actions: [
            {
              question_id: questionId,
              action,
              comment: comment?.trim() || undefined,
            },
          ],
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to apply review action: ${response.status}`);
      }

      const result: ExamPaperReviewResult = await response.json();
      if (!result.valid || !result.paper) {
        const errorMessage = result.errors[0]?.message || "审核动作应用失败";
        toast.error(errorMessage);
        return false;
      }

      setCurrentExamPaper(result.paper);
      const markdown = buildDraftMarkdownFromPaper(result.paper, currentExamValidation);
      setAnswer(markdown);
      setOrderedData([
        { type: "question", content: question } as QuestionData,
        { type: "report_complete", output: markdown } as Data,
      ]);
      toast.success(action === "approve" ? "已通过该题" : action === "reject" ? "已驳回该题" : "已标记为重生成");
      return true;
    } catch (error) {
      console.error("Exam review action error:", error);
      toast.error("审核动作提交失败");
      return false;
    } finally {
      setReviewingQuestionIds((prev) => prev.filter((id) => id !== questionId));
    }
  };

  const handleChat = async (message: string) => {
    if (!currentResearchId && !answer) {
      // On mobile, if there's no research yet, treat this as a new research request
      if (isMobile) {
        // Show immediate feedback for better UX
        setShowResult(true);
        setPromptValue(message); // Keep the message visible
        
        // Start the research with the chat message
        handleDisplayResult(message);
        return;
      }
    }
    
    setShowResult(true);
    setIsProcessingChat(true);
    setChatPromptValue("");
    
    // Create a user message
    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: Date.now()
    };
    
    // Add question to display in research results immediately
    const questionData: QuestionData = { type: 'question', content: message };
    setOrderedData(prevOrder => [...prevOrder, questionData]);
    
    // Add user message to history asynchronously
    if (currentResearchId) {
      addChatMessage(currentResearchId, userMessage).catch(error => {
        console.error('Error adding chat message to history:', error);
      });
    }
    
    // Mobile implementation - simplified for chat only
    if (isMobile) {
      try {
        // Direct API call instead of websockets
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: [{ role: 'user', content: message }],
            report: answer || '',
          }),
        });
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.response && data.response.content) {
          // Add AI response to chat history asynchronously
          if (currentResearchId) {
            addChatMessage(currentResearchId, data.response).catch(error => {
              console.error('Error adding AI response to history:', error);
            });
            
            // Also update the research with the new messages
            const chatData: ChatData = { 
              type: 'chat', 
              content: data.response.content,
              metadata: data.response.metadata 
            };
            
            setOrderedData(prevOrder => [...prevOrder, chatData]);
            
            // Get current ordered data and add new messages
            const updatedOrderedData = [...orderedData, questionData, chatData];
            
            // Update research in history
            updateResearch(
              currentResearchId, 
              answer, 
              updatedOrderedData
            ).catch(error => {
              console.error('Error updating research:', error);
            });
          } else {
            // If no research ID, just update the UI
            setOrderedData(prevOrder => [...prevOrder, { 
              type: 'chat', 
              content: data.response.content,
              metadata: data.response.metadata
            } as ChatData]);
          }
        } else {
          // Show error message
          setOrderedData(prevOrder => [...prevOrder, { 
            type: 'chat', 
            content: 'Sorry, something went wrong. Please try again.' 
          } as ChatData]);
        }
      } catch (error) {
        console.error('Error during chat:', error);
        
        // Add error message
        setOrderedData(prevOrder => [...prevOrder, { 
          type: 'chat', 
          content: 'Sorry, there was an error processing your request. Please try again.' 
        } as ChatData]);
      } finally {
        setIsProcessingChat(false);
      }
      return;
    }
    
    // Desktop implementation (unchanged)
    try {
      // Fetch all chat messages for this research
      let chatMessages: { role: string; content: string }[] = [];
      
      if (currentResearchId) {
        // If we have a research ID, get all messages from history
        chatMessages = getChatMessages(currentResearchId);
      }
      
      // Format messages to ensure they only contain role and content properties
      const formattedMessages = [...chatMessages, userMessage].map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      
      // Call the chat API
      const response = await fetch(`/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report: answer || "",
          messages: formattedMessages
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to get chat response: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.response) {
        // Check if response contains valid content
        if (!data.response.content) {
          console.error('Response content is null or empty');
          // Show error message in results
          setOrderedData(prevOrder => [...prevOrder, { 
            type: 'chat', 
            content: 'I apologize, but I couldn\'t generate a proper response. Please try asking your question again.' 
          }]);
        } else {
          // Add AI response to chat history asynchronously
          if (currentResearchId) {
            addChatMessage(currentResearchId, data.response).catch(error => {
              console.error('Error adding AI response to history:', error);
            });
          }
          
          // Add response to display in research results
          setOrderedData(prevOrder => {
            return [...prevOrder, { 
              type: 'chat', 
              content: data.response.content,
              metadata: data.response.metadata
            }];
          });
        }
        
        // Explicitly enable chat mode after getting a response
        if (!isInChatMode) {
          setIsInChatMode(true);
        }
      } else {
        // Show error message
        setOrderedData(prevOrder => [...prevOrder, { 
          type: 'chat', 
          content: 'Sorry, something went wrong. Please try again.' 
        }]);
      }
    } catch (error) {
      console.error('Error during chat:', error);
      
      // Add error message to display
      setOrderedData(prevOrder => [...prevOrder, { 
        type: 'chat', 
        content: 'Sorry, there was an error processing your request. Please try again.' 
      }]);
    } finally {
      setLoading(false);
      setIsProcessingChat(false);
    }
  };

  const handleDisplayResult = async (newQuestion: string) => {
    // Exit chat mode when starting a new research
    setIsInChatMode(false);
    setShowResult(true);
    setLoading(true);
    setQuestion(newQuestion);
    setPromptValue("");
    setAnswer("");
    setCurrentResearchId(null); // Reset current research ID for new research
    setCurrentExamPaper(null);
    setCurrentExamValidation(null);
    setReviewingQuestionIds([]);
    setOrderedData((prevOrder) => [...prevOrder, { type: 'question', content: newQuestion }]);

    // For mobile, use a simplified approach without websockets
    if (isMobile) {
      try {
        // Create a new unique ID for this research
        const newResearchId = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        
        // First save the initial question to history - with proper parameters
        const initialOrderedData: Data[] = [{ type: 'question', content: newQuestion } as QuestionData];
        await saveResearch(
          newQuestion,  // question
          '',           // empty answer initially
          initialOrderedData  // ordered data
        );
        
        // Make direct API call to get response
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: [{ role: 'user', content: newQuestion }],
            // No report since this is a new research
          }),
        });
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.response && data.response.content) {
          // Add the AI response to the ordered data
          const chatData: ChatData = { 
            type: 'chat', 
            content: data.response.content,
            metadata: data.response.metadata 
          };
          
          // Set the answer
          const chatAnswer = data.response.content;
          setAnswer(chatAnswer);
          setOrderedData(prevOrder => [...prevOrder, chatData]);
          
          // Update the research with the answer
          const updatedOrderedData: Data[] = [
            { type: 'question', content: newQuestion } as QuestionData,
            chatData
          ];
          
          // Save the completed research with proper parameters
          await updateResearch(
            newResearchId,    // id
            chatAnswer,       // answer
            updatedOrderedData // ordered data
          );
          
          // Set current research ID so we can continue the conversation
          setCurrentResearchId(newResearchId);
        } else {
          // Handle error
          setOrderedData(prevOrder => [...prevOrder, { 
            type: 'chat', 
            content: 'Sorry, I couldn\'t generate a research response. Please try again.' 
          } as ChatData]);
        }
      } catch (error) {
        console.error('Error in mobile research:', error);
        // Show error message
        setOrderedData(prevOrder => [...prevOrder, { 
          type: 'chat', 
          content: 'Sorry, there was an error processing your request. Please try again.' 
        } as ChatData]);
      } finally {
        setLoading(false);
      }
      return;
    }

    const storedConfig = localStorage.getItem('apiVariables');
    const apiVariables = storedConfig ? JSON.parse(storedConfig) : {};
    const langgraphHostUrl = apiVariables.LANGGRAPH_HOST_URL;

    // Starting new research - tracking for redirection once complete
    const newResearchStarted = Date.now().toString();
    // We'll use this as a temporary ID to keep track of this research
    const tempResearchId = `temp-${newResearchStarted}`;

    if (chatBoxSettings.report_type === 'multi_agents' && langgraphHostUrl) {
      let { streamResponse, host, thread_id } = await startLanggraphResearch(newQuestion, chatBoxSettings.report_source, langgraphHostUrl);
      const langsmithGuiLink = `https://smith.langchain.com/studio/thread/${thread_id}?baseUrl=${host}`;
      setOrderedData((prevOrder) => [...prevOrder, { type: 'langgraphButton', link: langsmithGuiLink }]);

      let previousChunk = null;
      for await (const chunk of streamResponse) {
        if (chunk.data.report != null && chunk.data.report != "Full report content here") {
          setOrderedData((prevOrder) => [...prevOrder, { ...chunk.data, output: chunk.data.report, type: 'report' }]);
          setLoading(false);
        
          // Save research and navigate to its unique URL once it's complete
          setAnswer(chunk.data.report);
        } else if (previousChunk) {
          const differences = findDifferences(previousChunk, chunk);
          setOrderedData((prevOrder) => [...prevOrder, { type: 'differences', content: 'differences', output: JSON.stringify(differences) }]);
        }
        previousChunk = chunk;
      }
    } else {
      initializeWebSocket(newQuestion, chatBoxSettings);
    }
  };

  // Mobile-specific implementation for research
  const handleMobileDisplayResult = async (newQuestion: string) => {
    // Update UI state
    setIsInChatMode(false);
    setShowResult(true);
    setLoading(true);
    setQuestion(newQuestion);
    setPromptValue("");
    setAnswer("");
    setCurrentResearchId(null);
    setCurrentExamPaper(null);
    setCurrentExamValidation(null);
    setReviewingQuestionIds([]);
    
    // Start with just the question
    setOrderedData([{ type: 'question', content: newQuestion } as QuestionData]);
    
    try {
      // Generate unique ID for this research
      const mobileResearchId = `mobile-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      
      // Save initial research with just the question
      const initialOrderedData: Data[] = [{ type: 'question', content: newQuestion } as QuestionData];
      
      // Save to research history
      await saveResearch(
        newQuestion,  // question
        '',           // empty answer initially
        initialOrderedData  // ordered data
      );
      
      // Make direct API call instead of using websockets
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [{ role: 'user', content: newQuestion }],
          // Include the required parameters
          report: '',  // No report since this is a new research
          report_source: chatBoxSettings.report_source || 'web',
          tone: chatBoxSettings.tone || 'Objective'
        }),
        // Set reasonable timeout
        signal: AbortSignal.timeout(30000) // 30-second timeout
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.response && data.response.content) {
        // Extract the response
        const responseContent = data.response.content;
        
        // Update UI with the answer
        setAnswer(responseContent);
        
        // Create chat data object
        const chatData: ChatData = { 
          type: 'chat', 
          content: responseContent,
          metadata: data.response.metadata 
        };
        
        // Update ordered data to include the response
        setOrderedData(prevData => [...prevData, chatData]);
        
        // Update the complete research
        const updatedOrderedData: Data[] = [
          { type: 'question', content: newQuestion } as QuestionData,
          chatData
        ];
        
        // Update research history with the answer
        await updateResearch(
          mobileResearchId,
          responseContent,
          updatedOrderedData
        );
        
        // Set current research ID for future interactions
        setCurrentResearchId(mobileResearchId);
      } else {
        // Handle error in response
        setOrderedData(prevData => [
          ...prevData, 
          { 
            type: 'chat', 
            content: "I'm sorry, I couldn't generate a complete response. Please try rephrasing your question." 
          } as ChatData
        ]);
      }
    } catch (error) {
      console.error('Mobile research error:', error);
      
      // Show error in UI
      setOrderedData(prevData => [
        ...prevData, 
        { 
          type: 'chat', 
          content: "Sorry, there was an error processing your request. Please try again." 
        } as ChatData
      ]);
    } finally {
      // Always finish loading state
      setLoading(false);
    }
  };

  // Mobile-specific chat handler
  const handleMobileChat = async (message: string) => {
    // Set states for UI feedback
    setIsProcessingChat(true);
    
    // Format user message
    const userMessage = {
      role: 'user',
      content: message
    };
    
    // Add question to UI immediately
    const questionData: QuestionData = { 
      type: 'question', 
      content: message 
    };
    
    setOrderedData(prevOrder => [...prevOrder, questionData]);
    
    try {
      // Direct API call instead of websockets
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [userMessage],
          report: answer || '',
          report_source: chatBoxSettings.report_source || 'web',
          tone: chatBoxSettings.tone || 'Objective'
        }),
        // Set reasonable timeout
        signal: AbortSignal.timeout(20000) // 20-second timeout
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.response && data.response.content) {
        // Add AI response to chat history asynchronously
        if (currentResearchId) {
          addChatMessage(currentResearchId, data.response).catch(error => {
            console.error('Error adding AI response to history:', error);
          });
          
          // Also update the research with the new messages
          const chatData: ChatData = { 
            type: 'chat', 
            content: data.response.content,
            metadata: data.response.metadata 
          };
          
          setOrderedData(prevOrder => [...prevOrder, chatData]);
          
          // Get current ordered data and add new messages
          const updatedOrderedData = [...orderedData, questionData, chatData];
          
          // Update research in history
          updateResearch(
            currentResearchId, 
            answer, 
            updatedOrderedData
          ).catch(error => {
            console.error('Error updating research:', error);
          });
        } else {
          // If no research ID, just update the UI
          setOrderedData(prevOrder => [...prevOrder, { 
            type: 'chat', 
            content: data.response.content,
            metadata: data.response.metadata
          } as ChatData]);
        }
      } else {
        // Show error message
        setOrderedData(prevOrder => [...prevOrder, { 
          type: 'chat', 
          content: 'Sorry, something went wrong. Please try again.' 
        } as ChatData]);
      }
    } catch (error) {
      console.error('Error during mobile chat:', error);
      
      // Add error message
      setOrderedData(prevOrder => [...prevOrder, { 
        type: 'chat', 
        content: 'Sorry, there was an error processing your request. Please try again.' 
      } as ChatData]);
    } finally {
      setIsProcessingChat(false);
      setChatPromptValue('');
    }
  };

  const reset = () => {
    // Reset UI states
    setShowResult(false);
    setPromptValue("");
    setIsStopped(false);
    setIsInChatMode(false);
    setCurrentResearchId(null); // Reset research ID
    setIsProcessingChat(false);
    setCurrentExamPaper(null);
    setCurrentExamValidation(null);
    setReviewingQuestionIds([]);
    
    // Clear previous research data
    setQuestion("");
    setAnswer("");
    setOrderedData([]);
    setAllLogs([]);

    // Reset feedback states
    setShowHumanFeedback(false);
    setQuestionForHuman(false);
    setExamDraft(createInitialExamDraft());
    
    // Clean up connections
    if (socket) {
      socket.close();
    }
    setLoading(false);
  };

  const handleClickSuggestion = (value: string) => {
    setPromptValue(value);
    const element = document.getElementById('input-area');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  /**
   * Handles stopping the current research
   * - Closes WebSocket connection
   * - Stops loading state
   * - Marks research as stopped
   * - Preserves current results
   * - Reloads the page to fully reset the connection
   */
  const handleStopResearch = () => {
    if (socket) {
      socket.close();
    }
    setLoading(false);
    setIsStopped(true);
    
    // Reload the page to completely reset the socket connection
    window.location.reload();
  };

  /**
   * Handles starting a new research
   * - Clears all previous research data and states
   * - Resets UI to initial state
   * - Closes any existing WebSocket connections
   */
  const handleStartNewResearch = () => {
    reset();
    setSidebarOpen(false);
  };

  const handleCopyUrl = () => {
    if (!currentResearchId) return;
    
    const url = `${window.location.origin}/research/${currentResearchId}`;
    navigator.clipboard.writeText(url)
      .then(() => {
        toast.success("URL copied to clipboard!");
      })
      .catch(() => {
        toast.error("Failed to copy URL");
      });
  };

  // Add a ref to track if an update is in progress to prevent infinite loops
  const isUpdatingRef = useRef(false);

  // Save or update research in history based on mode
  useEffect(() => {
    // Define an async function inside the effect
    const saveOrUpdateResearch = async () => {
      // Prevent infinite loops by checking if we're already updating
      if (isUpdatingRef.current) return;
      
      if (showResult && !loading && answer && question && orderedData.length > 0) {
        if (isInChatMode && currentResearchId) {
          // Prevent redundant updates by checking if data has changed
          try {
            const currentResearch = await getResearchById(currentResearchId);
            if (currentResearch && (currentResearch.answer !== answer || JSON.stringify(currentResearch.orderedData) !== JSON.stringify(orderedData))) {
              isUpdatingRef.current = true;
              await updateResearch(currentResearchId, answer, orderedData);
              // Reset the flag after a short delay to allow state updates to complete
              setTimeout(() => {
                isUpdatingRef.current = false;
              }, 100);
            }
          } catch (error) {
            console.error('Error updating research:', error);
            isUpdatingRef.current = false;
          }
        } else if (!isInChatMode) {
          // Check if this is a new research (not loaded from history)
          const isNewResearch = !history.some(item => 
            item.question === question && item.answer === answer
          );
          
          if (isNewResearch) {
            isUpdatingRef.current = true;
            try {
              const newId = await saveResearch(question, answer, orderedData);
              setCurrentResearchId(newId);
              
              // Don't navigate to the research page URL anymore
              // Just save the ID for sharing purposes
              
            } catch (error) {
              console.error('Error saving research:', error);
            } finally {
              // Reset the flag after a short delay to allow state updates to complete
              setTimeout(() => {
                isUpdatingRef.current = false;
              }, 100);
            }
          }
        }
      }
    };
    
    // Call the async function
    saveOrUpdateResearch();
  }, [showResult, loading, answer, question, orderedData, history, saveResearch, updateResearch, isInChatMode, currentResearchId, getResearchById]);

  // Handle selecting a research from history
  const handleSelectResearch = async (id: string) => {
    try {
      const research = await getResearchById(id);
      if (research) {
        // Navigate to the research page instead of loading it here
        router.push(`/research/${id}`);
      }
    } catch (error) {
      console.error('Error selecting research:', error);
      toast.error('Could not load the selected research');
    }
  };

  // Toggle sidebar
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  /**
   * Processes ordered data into logs for display
   * Updates whenever orderedData changes
   */
  useEffect(() => {
    const groupedData = preprocessOrderedData(orderedData);
    const statusReports = ["agent_generated", "starting_research", "planning_research", "error"];
    
    const newLogs = groupedData.reduce((acc: any[], data) => {
      // Process accordion blocks (grouped data)
      if (data.type === 'accordionBlock') {
        const logs = data.items.map((item: any, subIndex: any) => ({
          header: item.content,
          text: item.output,
          metadata: item.metadata,
          key: `${item.type}-${item.content}-${subIndex}`,
        }));
        return [...acc, ...logs];
      } 
      // Process status reports
      else if (statusReports.includes(data.content)) {
        return [...acc, {
          header: data.content,
          text: data.output,
          metadata: data.metadata,
          key: `${data.type}-${data.content}`,
        }];
      }
      return acc;
    }, []);
    
    setAllLogs(newLogs);
  }, [orderedData]);

  // Save chatBoxSettings to localStorage when they change
  useEffect(() => {
    localStorage.setItem('chatBoxSettings', JSON.stringify(chatBoxSettings));
  }, [chatBoxSettings]);

  // Set chat mode when a report is complete
  useEffect(() => {
    if (!isExamWorkflow && showResult && !loading && answer && !isInChatMode) {
      setIsInChatMode(true);
    }
  }, [showResult, loading, answer, isInChatMode, isExamWorkflow]);

  // Update the renderMobileContent function to use both mobile-specific functions
  const renderMobileContent = () => {
    if (!showResult) {
      return (
        <MobileHomeScreen
          examDraft={examDraft}
          setExamDraft={setExamDraft}
          handleValidateExamRequest={handleValidateExamRequest}
          isLoading={loading}
        />
      );
    } else {
      return (
        <MobileResearchContent
          orderedData={orderedData}
          answer={answer}
          loading={loading}
          isStopped={isStopped}
          chatPromptValue={chatPromptValue}
          setChatPromptValue={setChatPromptValue}
          handleChat={handleMobileChat} // Use mobile-specific chat handler
          isProcessingChat={isProcessingChat}
          onNewResearch={handleStartNewResearch}
          currentResearchId={currentResearchId || undefined}
          onShareClick={currentResearchId ? handleCopyUrl : undefined}
          workflowMode={chatBoxSettings.workflow_mode}
          examPaper={currentExamPaper}
          reviewingQuestionIds={reviewingQuestionIds}
          onReviewExamQuestion={handleReviewExamQuestion}
        />
      );
    }
  };

  return (
    <>
      {isMobile ? (
        // Mobile view - simplified layout with focus on chat
        getAppropriateLayout({
          loading,
          isStopped,
          showResult,
          onStop: handleStopResearch,
          onNewResearch: handleStartNewResearch,
          chatBoxSettings,
          setChatBoxSettings,
          mainContentRef,
          toggleSidebar,
          isProcessingChat,
          children: renderMobileContent()
        })
      ) : !showResult ? (
        // Desktop view - home page
        getAppropriateLayout({
          loading,
          isStopped,
          showResult,
          onStop: handleStopResearch,
          onNewResearch: handleStartNewResearch,
          chatBoxSettings,
          setChatBoxSettings,
          mainContentRef,
          showScrollButton,
          onScrollToBottom: scrollToBottom,
          children: (
            <>
              <ResearchSidebar
                history={history}
                onSelectResearch={handleSelectResearch}
                onNewResearch={handleStartNewResearch}
                onDeleteResearch={deleteResearch}
                isOpen={sidebarOpen}
                toggleSidebar={toggleSidebar}
              />
              
              <Hero
                examDraft={examDraft}
                setExamDraft={setExamDraft}
                handleValidateExamRequest={handleValidateExamRequest}
                loading={loading}
              />
            </>
          )
        })
      ) : (
        // Desktop view - research results
        getAppropriateLayout({
          loading,
          isStopped,
          showResult,
          onStop: handleStopResearch,
          onNewResearch: handleStartNewResearch,
          chatBoxSettings,
          setChatBoxSettings,
          mainContentRef,
          children: (
            <div className="relative">
              <ResearchSidebar
                history={history}
                onSelectResearch={handleSelectResearch}
                onNewResearch={handleStartNewResearch}
                onDeleteResearch={deleteResearch}
                isOpen={sidebarOpen}
                toggleSidebar={toggleSidebar}
              />
              
              {chatBoxSettings.layoutType === 'copilot' ? (
                <CopilotResearchContent
                  orderedData={orderedData}
                  answer={answer}
                  allLogs={allLogs}
                  chatBoxSettings={chatBoxSettings}
                  loading={loading}
                  isStopped={isStopped}
                  promptValue={promptValue}
                  chatPromptValue={chatPromptValue}
                  setPromptValue={setPromptValue}
                  setChatPromptValue={setChatPromptValue}
                  handleDisplayResult={handleDisplayResult}
                  handleChat={handleChat}
                  handleClickSuggestion={handleClickSuggestion}
                  currentResearchId={currentResearchId || undefined}
                  onShareClick={currentResearchId ? handleCopyUrl : undefined}
                  reset={reset}
                  isProcessingChat={isProcessingChat}
                  onNewResearch={handleStartNewResearch}
                  toggleSidebar={toggleSidebar}
                  examPaper={currentExamPaper}
                  reviewingQuestionIds={reviewingQuestionIds}
                  onReviewExamQuestion={handleReviewExamQuestion}
                />
              ) : (
                <ResearchContent
                  showResult={showResult}
                  orderedData={orderedData}
                  answer={answer}
                  allLogs={allLogs}
                  chatBoxSettings={chatBoxSettings}
                  loading={loading}
                  isInChatMode={isInChatMode}
                  isStopped={isStopped}
                  promptValue={promptValue}
                  chatPromptValue={chatPromptValue}
                  setPromptValue={setPromptValue}
                  setChatPromptValue={setChatPromptValue}
                  handleDisplayResult={handleDisplayResult}
                  handleChat={handleChat}
                  handleClickSuggestion={handleClickSuggestion}
                  currentResearchId={currentResearchId || undefined}
                  onShareClick={currentResearchId ? handleCopyUrl : undefined}
                  reset={reset}
                  isProcessingChat={isProcessingChat}
                  examPaper={currentExamPaper}
                  reviewingQuestionIds={reviewingQuestionIds}
                  onReviewExamQuestion={handleReviewExamQuestion}
                />
              )}
              
              {showHumanFeedback && false && (
                <HumanFeedback
                  questionForHuman={questionForHuman}
                  websocket={socket}
                  onFeedbackSubmit={handleFeedbackSubmit}
                />
              )}
            </div>
          )
        })
      )}
    </>
  );
}
