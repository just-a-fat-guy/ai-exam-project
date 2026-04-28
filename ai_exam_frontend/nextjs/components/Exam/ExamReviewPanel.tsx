"use client";

import { useMemo, useState } from "react";
import {
  ExamDraftData,
  ExamDraftQuestionSnapshot,
} from "@/types/exam";

interface ExamReviewPanelProps {
  paper: ExamDraftData;
  loadingQuestionIds?: string[];
  onReviewAction: (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration",
    comment?: string
  ) => Promise<boolean>;
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
  onReviewAction,
}: ExamReviewPanelProps) {
  const [comments, setComments] = useState<Record<string, string>>({});

  const questionCount = useMemo(
    () => paper.sections.reduce((sum, section) => sum + section.questions.length, 0),
    [paper.sections]
  );

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

  return (
    <div className="apple-panel-strong mb-4 rounded-[30px] border-white/8 p-5 shadow-[0_24px_70px_rgba(0,0,0,0.2)]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            人工审核
          </div>
          <h3 className="mt-1 text-lg font-medium text-white/88">试卷草案审核面板</h3>
          <p className="mt-1 text-sm text-white/52">
            当前草案共 {questionCount} 道题。这里可以直接对单题执行通过、驳回或要求重生成。
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3 text-sm text-white/70">
          <div>待审核：{paper.review_summary?.pending_review_count ?? 0}</div>
          <div>已通过：{paper.review_summary?.reviewed_count ?? 0}</div>
          <div>已驳回：{paper.review_summary?.rejected_count ?? 0}</div>
        </div>
      </div>

      <div className="space-y-4">
        {paper.sections.map((section) => (
          <div key={`${section.section_order}-${section.section_name}`} className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-white/84">{section.section_name}</div>
                <div className="text-xs text-white/45">
                  共 {section.question_count} 题，当前分值 {section.computed_section_score ?? "未完整推导"}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {section.questions.map((question) => {
                const loading = loadingQuestionIds.includes(question.question_id);
                return (
                  <div
                    key={question.question_id}
                    className="rounded-[22px] border border-white/8 bg-black/20 p-4"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
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
                    </div>

                    <div className="mb-3 text-sm leading-7 text-white/84">{question.stem}</div>

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
                          <div key={`${question.question_id}-comment-${index}`}>- {comment}</div>
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
          </div>
        ))}
      </div>
    </div>
  );
}
