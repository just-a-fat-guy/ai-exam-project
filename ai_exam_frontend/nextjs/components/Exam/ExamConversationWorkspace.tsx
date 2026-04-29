"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { markdownToHtml } from "@/helpers/markdownHelper";
import ChatInput from "@/components/ResearchBlocks/elements/ChatInput";
import ExamReviewPanel from "@/components/Exam/ExamReviewPanel";
import { ConversationThreadItem, Data } from "@/types/data";
import { ExamDraftData } from "@/types/exam";

interface ExamConversationWorkspaceProps {
  question: string;
  orderedData: Data[];
  answer: string;
  allLogs: Array<{
    header: string;
    text: string;
    metadata?: Record<string, unknown>;
    key: string;
  }>;
  examPaper?: ExamDraftData | null;
  chatPromptValue: string;
  setChatPromptValue: React.Dispatch<React.SetStateAction<string>>;
  onSubmit: (message: string) => void;
  loading: boolean;
  isProcessingChat: boolean;
  reviewingQuestionIds?: string[];
  applyingTeacherFeedback?: boolean;
  onReviewExamQuestion?: (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration",
    comment?: string
  ) => Promise<boolean>;
  onApplyTeacherFeedback?: (feedback: string) => Promise<boolean>;
  onNewConversation: () => void;
  onGoHome: () => void;
  activeTaskSummary?: string;
  activeLogs?: Array<{
    header: string;
    text: string;
    metadata?: Record<string, unknown>;
    key: string;
  }>;
}

interface RenderedAssistantBlockProps {
  content: string;
  examPaper?: ExamDraftData | null;
  logs: ExamConversationWorkspaceProps["allLogs"];
  reviewingQuestionIds?: string[];
  applyingTeacherFeedback?: boolean;
  onReviewExamQuestion?: ExamConversationWorkspaceProps["onReviewExamQuestion"];
  onApplyTeacherFeedback?: ExamConversationWorkspaceProps["onApplyTeacherFeedback"];
}

function ConversationBubble({
  role,
  children,
}: {
  role: "user" | "assistant" | "system";
  children: React.ReactNode;
}) {
  const isUser = role === "user";
  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[85%] rounded-[24px] bg-blue-500 px-5 py-4 text-base font-medium text-white shadow-[0_18px_40px_rgba(59,130,246,0.25)]"
            : "max-w-[92%] rounded-[28px] border border-white/8 bg-white/[0.04] px-5 py-5 text-white shadow-[0_20px_60px_rgba(0,0,0,0.26)] backdrop-blur-xl"
        }
      >
        {children}
      </div>
    </div>
  );
}

function AssistantMarkdownCard({
  content,
}: {
  content: string;
}) {
  const [htmlContent, setHtmlContent] = useState("");

  useEffect(() => {
    let mounted = true;
    markdownToHtml(content || "").then((html) => {
      if (mounted) {
        setHtmlContent(html);
      }
    });
    return () => {
      mounted = false;
    };
  }, [content]);

  return (
    <div className="markdown-content prose prose-invert max-w-none text-white/84">
      <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
    </div>
  );
}

function AssistantStatusStrip({
  taskSummary,
  logs,
}: {
  taskSummary: string;
  logs: ExamConversationWorkspaceProps["allLogs"];
}) {
  const [expanded, setExpanded] = useState(false);
  const latestLogs = logs.slice(-6);
  const latestSummary = latestLogs.map((item) => item.text).join(" · ");
  const latestStage = latestLogs[latestLogs.length - 1]?.header || "";
  const compactLogs = latestLogs.slice(-3);

  return (
    <div className="mb-4 space-y-2 text-xs text-white/46">
      {taskSummary ? (
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.2em] text-white/30">
              任务摘要
            </span>
            {latestStage ? (
              <span className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white/48">
                {latestStage}
              </span>
            ) : null}
          </div>
          <div className="line-clamp-1 text-white/58">{taskSummary}</div>
        </div>
      ) : null}

      {latestLogs.length > 0 ? (
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
          <div className="mb-1 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-white/30">
                Agent 工作过程
              </span>
              <span className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[10px] text-white/44">
                {latestLogs.length} 步
              </span>
            </div>
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="text-[11px] text-white/52 transition hover:text-white/80"
            >
              {expanded ? "收起" : "展开"}
            </button>
          </div>
          {expanded ? (
            <div className="space-y-1.5">
              {latestLogs.map((item) => (
                <div key={item.key} className="rounded-xl border border-white/6 bg-black/10 px-2.5 py-2 text-white/58">
                  <span className="mr-1 text-white/34">[{item.header}]</span>
                  {item.text}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              <div className="line-clamp-1 text-white/58">{latestSummary}</div>
              <div className="flex flex-wrap gap-1.5">
                {compactLogs.map((item) => (
                  <span
                    key={item.key}
                    className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[10px] text-white/46"
                  >
                    {item.header}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function RenderedAssistantBlock({
  content,
  examPaper,
  logs,
  reviewingQuestionIds = [],
  applyingTeacherFeedback = false,
  onReviewExamQuestion,
  onApplyTeacherFeedback,
}: RenderedAssistantBlockProps) {
  return (
    <div>
      <AssistantStatusStrip taskSummary={content.split("\n")[0] || ""} logs={logs} />
      {examPaper && onReviewExamQuestion ? (
        <div className="space-y-4">
          <ExamReviewPanel
            paper={examPaper}
            variant="embedded"
            loadingQuestionIds={reviewingQuestionIds}
            teacherFeedbackLoading={applyingTeacherFeedback}
            onReviewAction={onReviewExamQuestion}
            onApplyTeacherFeedback={onApplyTeacherFeedback}
          />
        </div>
      ) : (
        <AssistantMarkdownCard content={content} />
      )}
    </div>
  );
}

export default function ExamConversationWorkspace({
  question,
  orderedData,
  answer,
  allLogs,
  examPaper,
  chatPromptValue,
  setChatPromptValue,
  onSubmit,
  loading,
  isProcessingChat,
  reviewingQuestionIds = [],
  applyingTeacherFeedback = false,
  onReviewExamQuestion,
  onApplyTeacherFeedback,
  onNewConversation,
  onGoHome,
  activeTaskSummary = "",
  activeLogs = [],
}: ExamConversationWorkspaceProps) {
  const scrollBottomRef = useRef<HTMLDivElement>(null);

  const threadItems = useMemo<ConversationThreadItem[]>(() => {
    const items: ConversationThreadItem[] = [];

    orderedData.forEach((item, index) => {
      if (item.type === "question") {
        items.push({
          id: `question-${index}`,
          role: "user",
          kind: "message",
          content: item.content,
        });
        return;
      }

      if (item.type === "report" || item.type === "report_complete") {
        const reportMetadata = item.metadata || {};
        const reportExamPaper = (reportMetadata.examPaper as ExamDraftData | null | undefined) || null;
        items.push({
          id: `assistant-${index}`,
          role: "assistant",
          kind: reportExamPaper ? "exam_preview" : "message",
          content: item.output || item.content || "",
          metadata: reportMetadata,
        });
        return;
      }

      if (item.type === "chat") {
        items.push({
          id: `chat-${index}`,
          role: "assistant",
          kind: "message",
          content: item.content,
          metadata: item.metadata,
        });
      }
    });

    if (items.length === 0 && answer) {
      items.push({
        id: "assistant-fallback",
        role: "assistant",
        kind: examPaper ? "exam_preview" : "message",
        content: answer,
      });
    }

    if (items.length === 0 && question) {
      items.push({
        id: "question-fallback",
        role: "user",
        kind: "message",
        content: question,
      });
    }

    return items;
  }, [orderedData, answer, examPaper, question]);

  useEffect(() => {
    scrollBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threadItems, loading, isProcessingChat]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/32">
              AI Exam Conversation
            </div>
            <div className="text-lg font-semibold text-white/86">
              试卷对话工作区
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onGoHome}
              className="apple-button-secondary rounded-full px-4 py-2 text-sm font-medium"
            >
              返回首页
            </button>
            <button
              type="button"
              onClick={onNewConversation}
              className="apple-button-primary rounded-full px-4 py-2 text-sm font-medium"
            >
              新对话
            </button>
          </div>
        </div>
      </div>

      <div className="no-scrollbar flex-1 overflow-y-auto px-6 pb-32 pt-6 min-h-0">
        <div className="mx-auto flex max-w-5xl flex-col gap-6">
          {threadItems.length === 0 ? (
            <div className="rounded-[28px] border border-white/8 bg-white/[0.035] px-6 py-8 text-center text-white/58">
              <div className="mb-2 text-sm uppercase tracking-[0.18em] text-white/28">
                新对话
              </div>
              <div className="text-lg font-medium text-white/82">
                在下方直接输入教师组卷需求，Agent 会继续规划并生成试卷。
              </div>
            </div>
          ) : (
            threadItems.map((item, index) => {
              const isLatestAssistant = item.role === "assistant" && index === threadItems.length - 1;
              const itemExamPaper =
                (item.metadata?.examPaper as ExamDraftData | null | undefined) ||
                (isLatestAssistant ? examPaper : null);
              return (
                <ConversationBubble key={item.id} role={item.role}>
                  {item.role === "user" ? (
                    <div className="whitespace-pre-wrap break-words leading-7">{item.content}</div>
                  ) : (
                    <RenderedAssistantBlock
                      content={item.content}
                      examPaper={itemExamPaper}
                      logs={isLatestAssistant ? allLogs : []}
                      reviewingQuestionIds={reviewingQuestionIds}
                      applyingTeacherFeedback={applyingTeacherFeedback}
                      onReviewExamQuestion={onReviewExamQuestion}
                      onApplyTeacherFeedback={onApplyTeacherFeedback}
                    />
                  )}
                </ConversationBubble>
              );
            })
          )}

          {(loading || isProcessingChat) && (
            <ConversationBubble role="assistant">
              <AssistantStatusStrip
                taskSummary={activeTaskSummary || question || "Agent 正在处理请求"}
                logs={activeLogs.length ? activeLogs : allLogs}
              />
              <div className="rounded-[24px] border border-white/8 bg-white/[0.025] px-4 py-4 text-sm text-white/62">
                正在处理中，请稍候……
              </div>
            </ConversationBubble>
          )}

          <div ref={scrollBottomRef} />
        </div>
      </div>

      <div className="sticky bottom-0 z-10 px-6 pb-5 pt-3">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-[32px] border border-white/8 bg-black/30 p-3 shadow-[0_24px_80px_rgba(0,0,0,0.38)] backdrop-blur-2xl">
            <ChatInput
              promptValue={chatPromptValue}
              setPromptValue={setChatPromptValue}
              handleSubmit={onSubmit}
              disabled={loading || isProcessingChat}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
