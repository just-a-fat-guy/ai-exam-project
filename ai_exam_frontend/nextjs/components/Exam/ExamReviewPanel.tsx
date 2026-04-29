"use client";

import { useMemo, useState } from "react";
import {
  ExamDraftData,
  ExamDraftQuestionSnapshot,
} from "@/types/exam";

interface ExamReviewPanelProps {
  paper: ExamDraftData;
  loadingQuestionIds?: string[];
  teacherFeedbackLoading?: boolean;
  variant?: "full" | "embedded";
  onReviewAction: (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration",
    comment?: string
  ) => Promise<boolean>;
  onApplyTeacherFeedback?: (feedback: string) => Promise<boolean>;
}

const reviewStatusLabelMap: Record<string, string> = {
  pending_review: "待审核",
  reviewed: "已通过",
  rejected: "已驳回",
};

const draftStatusLabelMap: Record<string, string> = {
  template_preview: "模板预览",
  generated_preview: "AI 已生成",
  pending_regeneration: "待重生成",
};

const issueColorMap: Record<string, string> = {
  error: "border-red-400/30 bg-red-400/10 text-red-200",
  warning: "border-amber-400/30 bg-amber-400/10 text-amber-100",
};

function formatAnswer(value: string | string[] | null | undefined) {
  if (!value) {
    return "未提供";
  }
  return Array.isArray(value) ? value.join("、") : value;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function ExpandableText({
  text,
  collapsedLines = 4,
  className = "",
}: {
  text: string;
  collapsedLines?: 2 | 3 | 4 | 5 | 6;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const shouldCollapse = text.trim().length > 120 || text.includes("\n");
  const clampClassMap = {
    2: "line-clamp-2",
    3: "line-clamp-3",
    4: "line-clamp-4",
    5: "line-clamp-5",
    6: "line-clamp-6",
  } as const;

  return (
    <div>
      <div
        className={`whitespace-pre-wrap break-words ${
          !expanded && shouldCollapse ? clampClassMap[collapsedLines] : ""
        } ${className}`}
      >
        {text}
      </div>
      {shouldCollapse ? (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="mt-2 text-xs text-white/48 transition hover:text-white/78"
        >
          {expanded ? "收起" : "展开更多"}
        </button>
      ) : null}
    </div>
  );
}

function SnapshotCard({
  title,
  snapshot,
  tone,
}: {
  title: string;
  snapshot: ExamDraftQuestionSnapshot;
  tone: "previous" | "current";
}) {
  const toneClasses =
    tone === "current"
      ? "border-emerald-400/18 bg-emerald-400/[0.06]"
      : "border-white/8 bg-white/[0.03]";

  return (
    <div className={`rounded-[20px] border p-4 ${toneClasses}`}>
      <div className="mb-3 text-xs uppercase tracking-[0.2em] text-white/42">{title}</div>
      <div className="space-y-3 text-sm text-white/76">
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-white/34">题干</div>
          <div className="leading-7 text-white/84">{snapshot.stem}</div>
        </div>

        {snapshot.options.length > 0 && (
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-white/34">选项</div>
            <div className="space-y-1 text-white/70">
              {snapshot.options.map((option) => (
                <div key={`${title}-${option.label}`}>
                  {option.label}. {option.content}
                  {option.is_correct ? "  [正确]" : ""}
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-white/34">参考答案</div>
          <div>{formatAnswer(snapshot.reference_answer)}</div>
        </div>

        {snapshot.explanation && (
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-white/34">解析</div>
            <div className="leading-6 text-white/68">{snapshot.explanation}</div>
          </div>
        )}

        {snapshot.knowledge_points.length > 0 && (
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-white/34">知识点</div>
            <div>{snapshot.knowledge_points.join("、")}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ExamReviewPanel({
  paper,
  loadingQuestionIds = [],
  teacherFeedbackLoading = false,
  variant = "full",
  onReviewAction,
  onApplyTeacherFeedback,
}: ExamReviewPanelProps) {
  const [comments, setComments] = useState<Record<string, string>>({});
  const [teacherFeedback, setTeacherFeedback] = useState("");
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [expandedQuestions, setExpandedQuestions] = useState<Record<string, boolean>>({});
  const [showGuidance, setShowGuidance] = useState(false);
  const [showFeedbackHistory, setShowFeedbackHistory] = useState(false);

  const questionCount = useMemo(
    () => paper.sections.reduce((sum, section) => sum + section.questions.length, 0),
    [paper.sections]
  );
  const isEmbedded = variant === "embedded";

  const isSectionExpanded = (sectionKey: string) => expandedSections[sectionKey] ?? true;
  const isQuestionExpanded = (questionId: string) => expandedQuestions[questionId] ?? !isEmbedded;

  const toggleSection = (sectionKey: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionKey]: !(prev[sectionKey] ?? true),
    }));
  };

  const toggleQuestion = (questionId: string) => {
    setExpandedQuestions((prev) => ({
      ...prev,
      [questionId]: !(prev[questionId] ?? !isEmbedded),
    }));
  };

  const handleAction = async (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration"
  ) => {
    const comment = comments[questionId]?.trim();
    const success = await onReviewAction(questionId, action, comment || undefined);
    if (success && action !== "approve") {
      setComments((prev) => ({ ...prev, [questionId]: "" }));
    }
  };

  const handleTeacherFeedbackSubmit = async () => {
    const feedback = teacherFeedback.trim();
    if (!feedback || !onApplyTeacherFeedback) {
      return;
    }
    const success = await onApplyTeacherFeedback(feedback);
    if (success) {
      setTeacherFeedback("");
    }
  };

  return (
    <div
      className={
        isEmbedded
          ? "space-y-4 rounded-[26px] border border-white/8 bg-white/[0.03] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.18)]"
          : "apple-panel-strong mb-4 rounded-[30px] border-white/8 p-5 shadow-[0_24px_70px_rgba(0,0,0,0.2)]"
      }
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            {isEmbedded ? "Assistant Exam Card" : "人工审核"}
          </div>
          <h3 className="mt-1 text-lg font-medium text-white/88">
            {isEmbedded ? paper.paper_title : "试卷草案审核面板"}
          </h3>
          <p className="mt-1 text-sm text-white/52">
            {isEmbedded
              ? `当前草案共 ${questionCount} 道题。你可以直接在消息里审核单题，或继续让 Agent 调整整卷。`
              : `当前草案共 ${questionCount} 道题。这里可以直接对单题执行通过、驳回或要求重生成。`}
          </p>
        </div>
        <div className="min-w-[132px] rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3 text-sm text-white/70">
          <div>待审核：{paper.review_summary?.pending_review_count ?? 0}</div>
          <div>已通过：{paper.review_summary?.reviewed_count ?? 0}</div>
          <div>已驳回：{paper.review_summary?.rejected_count ?? 0}</div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
          {paper.meta.grade} / {paper.meta.exam_type}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
          题量 {paper.totals.computed_question_count}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
          总分 {paper.totals.requested_total_score ?? paper.quality_summary.computed_total_score ?? "未定"}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
          修订轮次 {paper.revision_round}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
          {paper.generation_stage}
        </span>
      </div>

      {onApplyTeacherFeedback ? (
        <div className="mb-4 rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
          <div className="mb-2 text-sm font-medium text-white/84">整卷反馈 Agent</div>
          <p className="mb-3 text-sm text-white/52">
            直接告诉系统你想怎样改卷，例如“整体偏难，把应用题降一点，作文题换成半命题”。
          </p>
          <textarea
            value={teacherFeedback}
            onChange={(event) => setTeacherFeedback(event.target.value)}
            placeholder="输入教师整卷反馈，Agent 会先决定改哪些题，再调用大模型执行修改或替换。"
            className="min-h-[120px] w-full rounded-[20px] border border-white/10 bg-black/20 px-4 py-3 text-sm leading-7 text-white/84 outline-none transition placeholder:text-white/28 focus:border-white/20"
          />
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={handleTeacherFeedbackSubmit}
              disabled={teacherFeedbackLoading || !teacherFeedback.trim()}
              className="apple-button-primary rounded-full px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-45"
            >
              {teacherFeedbackLoading ? "Agent 处理中..." : "让 Agent 处理整卷反馈"}
            </button>
          </div>
        </div>
      ) : null}

      {(paper.paper_level_guidance.length > 0 || paper.feedback_history.length > 0) && (
        <div className="mb-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="mb-2 text-sm font-medium text-white/84">
              当前整卷指导
            </div>
            <div className="text-xs text-white/45">修订轮次：第 {paper.revision_round} 轮</div>
            <div className="mt-3 space-y-2 text-sm text-white/76">
              {paper.paper_level_guidance.length > 0 ? (
                <>
                {(showGuidance ? paper.paper_level_guidance : paper.paper_level_guidance.slice(0, 2)).map((item, index) => (
                  <div key={`guidance-${index}`} className="rounded-2xl border border-white/8 bg-black/20 px-3 py-2">
                    <ExpandableText text={item} collapsedLines={2} className="text-sm text-white/76" />
                  </div>
                ))}
                {paper.paper_level_guidance.length > 2 ? (
                  <button
                    type="button"
                    onClick={() => setShowGuidance((prev) => !prev)}
                    className="text-xs text-white/46 transition hover:text-white/78"
                  >
                    {showGuidance ? "收起指导" : `展开其余 ${paper.paper_level_guidance.length - 2} 条指导`}
                  </button>
                ) : null}
                </>
              ) : (
                <div className="text-white/42">当前还没有沉淀出的整卷级指导。</div>
              )}
            </div>
          </div>

          <div className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="mb-2 text-sm font-medium text-white/84">教师反馈记忆</div>
            <div className="space-y-3">
              {paper.feedback_history.length > 0 ? (
                <>
                {(showFeedbackHistory ? [...paper.feedback_history].slice(-8) : [...paper.feedback_history].slice(-3))
                  .reverse()
                  .map((record, index) => (
                  <div key={`${record.timestamp}-${index}`} className="rounded-[18px] border border-white/8 bg-black/20 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs uppercase tracking-[0.18em] text-white/34">
                        {record.strategy}
                      </div>
                      <div className="text-xs text-white/42">{formatTimestamp(record.timestamp)}</div>
                    </div>
                    <div className="mt-2 text-sm text-white/84">
                      <ExpandableText text={record.summary} collapsedLines={2} className="text-sm text-white/84" />
                    </div>
                    <div className="mt-2 text-xs leading-6 text-white/54">
                      反馈：
                      <ExpandableText
                        text={record.teacher_feedback}
                        collapsedLines={3}
                        className="mt-1 text-xs leading-6 text-white/54"
                      />
                    </div>
                    {record.target_sections.length > 0 && (
                      <div className="mt-2 text-xs text-white/50">
                        命中大题：{record.target_sections.join("、")}
                      </div>
                    )}
                    {record.target_question_ids.length > 0 && (
                      <div className="mt-2 text-xs text-white/50">
                        命中题目：{record.target_question_ids.join("、")}
                      </div>
                    )}
                    {record.paper_level_guidance.length > 0 && (
                      <div className="mt-2 text-xs text-white/50">
                        指导：{record.paper_level_guidance.join("；")}
                      </div>
                    )}
                  </div>
                ))}
                {paper.feedback_history.length > 3 ? (
                  <button
                    type="button"
                    onClick={() => setShowFeedbackHistory((prev) => !prev)}
                    className="text-xs text-white/46 transition hover:text-white/78"
                  >
                    {showFeedbackHistory ? "收起历史反馈" : `展开更多反馈 (${paper.feedback_history.length - 3})`}
                  </button>
                ) : null}
                </>
              ) : (
                <div className="text-sm text-white/42">当前还没有整卷反馈历史。</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {paper.sections.map((section) => (
          <div
            key={`${section.section_order}-${section.section_name}`}
            className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-white/84">{section.section_name}</div>
                <div className="text-xs text-white/45">
                  共 {section.question_count} 题，当前分值 {section.computed_section_score ?? "未完整推导"}
                </div>
              </div>
              <button
                type="button"
                onClick={() => toggleSection(`${section.section_order}-${section.section_name}`)}
                className="text-xs text-white/46 transition hover:text-white/78"
              >
                {isSectionExpanded(`${section.section_order}-${section.section_name}`) ? "收起大题" : "展开大题"}
              </button>
            </div>

            {isSectionExpanded(`${section.section_order}-${section.section_name}`) ? (
            <div className="space-y-3">
              {section.questions.map((question) => {
                const loading = loadingQuestionIds.includes(question.question_id);
                return (
                  <div
                    key={question.question_id}
                    className="rounded-[22px] border border-white/8 bg-black/20 p-4 shadow-[0_10px_30px_rgba(0,0,0,0.12)]"
                  >
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
                        {question.question_id}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
                        {draftStatusLabelMap[question.draft_status] || question.draft_status}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
                        {reviewStatusLabelMap[question.review_status] || question.review_status}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
                        分值 {question.score ?? "未设"}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-white/70">
                        {question.question_type}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleQuestion(question.question_id)}
                        className="ml-auto text-xs text-white/46 transition hover:text-white/78"
                      >
                        {isQuestionExpanded(question.question_id) ? "收起详情" : "展开详情"}
                      </button>
                    </div>

                    <div className="mb-3 text-sm leading-7 text-white/84">
                      <ExpandableText text={question.stem} collapsedLines={4} className="text-sm leading-7 text-white/84" />
                    </div>

                    {question.options.length > 0 && isQuestionExpanded(question.question_id) && (
                      <div className="mb-3 grid gap-2 sm:grid-cols-2">
                        {question.options.map((option) => (
                          <div
                            key={`${question.question_id}-${option.label}`}
                            className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2 text-sm text-white/72"
                          >
                            <span className="mr-2 text-white/42">{option.label}.</span>
                            {option.content}
                          </div>
                        ))}
                      </div>
                    )}

                    {isQuestionExpanded(question.question_id) ? (
                      <>
                      <div className="mb-3 grid gap-3 lg:grid-cols-2">
                        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-white/34">参考答案</div>
                          <ExpandableText
                            text={formatAnswer(question.reference_answer)}
                            collapsedLines={3}
                            className="text-sm text-white/76"
                          />
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-white/34">知识点</div>
                          <div className="text-sm text-white/76">
                            {question.knowledge_points.length > 0 ? question.knowledge_points.join("、") : "未标注"}
                          </div>
                        </div>
                      </div>

                      {question.explanation && (
                        <div className="mb-3 rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-white/34">解析</div>
                          <ExpandableText
                            text={question.explanation}
                            collapsedLines={4}
                            className="text-sm leading-7 text-white/70"
                          />
                        </div>
                      )}
                      </>
                    ) : null}

                    {question.last_regeneration_diff && (
                      <div className="mb-3 rounded-[22px] border border-sky-400/16 bg-sky-400/[0.05] p-4">
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <div className="text-xs uppercase tracking-[0.2em] text-sky-100/55">
                              最近一次重生成对比
                            </div>
                            <div className="mt-1 text-sm text-white/78">
                              生成时间：{formatTimestamp(question.last_regeneration_diff.regenerated_at)}
                            </div>
                          </div>
                          {question.last_regeneration_diff.comment && (
                            <div className="max-w-[420px] text-xs leading-6 text-sky-50/72">
                              触发原因：{question.last_regeneration_diff.comment}
                            </div>
                          )}
                        </div>

                        <div className="grid gap-3 lg:grid-cols-2">
                          <SnapshotCard
                            title="旧题目"
                            snapshot={question.last_regeneration_diff.previous}
                            tone="previous"
                          />
                          <SnapshotCard
                            title="新题目"
                            snapshot={question.last_regeneration_diff.current}
                            tone="current"
                          />
                        </div>
                      </div>
                    )}

                    {question.quality_issues.length > 0 && (
                      <div className="mb-3 flex flex-wrap gap-2">
                        {question.quality_issues.map((issue, index) => (
                          <span
                            key={`${question.question_id}-${issue.code}-${index}`}
                            className={`rounded-full border px-3 py-1 text-xs ${issueColorMap[issue.level] || issueColorMap.warning}`}
                          >
                            {issue.level === "error" ? "错误" : "警告"}：{issue.message}
                          </span>
                        ))}
                      </div>
                    )}

                    {question.review_comments.length > 0 && (
                      <div className="mb-3 rounded-2xl border border-white/8 bg-white/[0.03] p-3 text-sm text-white/64">
                        <div className="mb-1 text-xs uppercase tracking-[0.2em] text-white/36">历史审核备注</div>
                        {question.review_comments.map((comment, index) => (
                          <div key={`${question.question_id}-comment-${index}`}>
                            - <ExpandableText text={comment} collapsedLines={2} className="inline text-sm text-white/64" />
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="space-y-3">
                      <textarea
                        value={comments[question.question_id] ?? ""}
                        onChange={(event) =>
                          setComments((prev) => ({
                            ...prev,
                            [question.question_id]: event.target.value,
                          }))
                        }
                        placeholder="驳回或要求重生成时，请填写审核原因。"
                        className="min-h-[86px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/84 outline-none transition focus:border-white/20 focus:bg-white/[0.06]"
                      />

                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => handleAction(question.question_id, "approve")}
                          disabled={loading}
                          className="rounded-full border border-emerald-400/30 bg-emerald-400/12 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-400/18 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {loading ? "处理中..." : "通过"}
                        </button>
                        <button
                          onClick={() => handleAction(question.question_id, "reject")}
                          disabled={loading}
                          className="rounded-full border border-red-400/30 bg-red-400/12 px-4 py-2 text-sm text-red-100 transition hover:bg-red-400/18 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {loading ? "处理中..." : "驳回"}
                        </button>
                        <button
                          onClick={() => handleAction(question.question_id, "request_regeneration")}
                          disabled={loading}
                          className="rounded-full border border-amber-400/30 bg-amber-400/12 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-400/18 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {loading ? "处理中..." : "重生成"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
