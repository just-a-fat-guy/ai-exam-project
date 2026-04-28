import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ResearchHistoryItem } from '@/types/data';
import { useResearchHistoryContext } from '@/hooks/ResearchHistoryContext';
import LoadingDots from '@/components/LoadingDots';
import { toast } from "react-hot-toast";
import ExamRequestForm from '@/components/Exam/ExamRequestForm';
import { ExamRequestDraft } from '@/types/exam';

interface MobileHomeScreenProps {
  examDraft: ExamRequestDraft;
  setExamDraft: React.Dispatch<React.SetStateAction<ExamRequestDraft>>;
  handleValidateExamRequest: () => Promise<void>;
  isLoading?: boolean;
}

export default function MobileHomeScreen({
  examDraft,
  setExamDraft,
  handleValidateExamRequest,
  isLoading = false,
}: MobileHomeScreenProps) {
  const { history } = useResearchHistoryContext();
  const [recentHistory, setRecentHistory] = useState<ResearchHistoryItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submissionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Get recent research history
  useEffect(() => {
    // Get the 3 most recent items
    if (history && history.length > 0) {
      setRecentHistory(history.slice(0, 3));
    }
  }, [history]);

  // Clean up any timeouts on unmount
  useEffect(() => {
    return () => {
      if (submissionTimeoutRef.current) {
        clearTimeout(submissionTimeoutRef.current);
      }
    };
  }, []);

  // Handle history item click
  const handleHistoryItemClick = useCallback((id: string) => {
    window.location.href = `/research/${id}`;
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!examDraft.paper_title.trim() || isLoading || isSubmitting) {
      return;
    }
    
    try {
      // Set submitting state for UI feedback
      setIsSubmitting(true);
      
      // Add a timeout as a safety measure to prevent infinite loading
      submissionTimeoutRef.current = setTimeout(() => {
        setIsSubmitting(false);
        toast.error("研究请求耗时过长，请重试。", {
          duration: 3000,
          position: "bottom-center"
        });
      }, 15000); // 15 second timeout
      
      try {
        await handleValidateExamRequest();
        
        // Clear the timeout since we successfully completed
        if (submissionTimeoutRef.current) {
          clearTimeout(submissionTimeoutRef.current);
          submissionTimeoutRef.current = null;
        }
      } catch (apiError) {
        console.error("API error during research submission:", apiError);
        toast.error("提交研究任务时出现问题，请重试。", {
          duration: 3000,
          position: "bottom-center"
        });
        
        // Clear submission state
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error("Error during research submission:", error);
      // Reset state in case of error
      setIsSubmitting(false);
      
      // Clear any existing timeout
      if (submissionTimeoutRef.current) {
        clearTimeout(submissionTimeoutRef.current);
        submissionTimeoutRef.current = null;
      }
    }
  }, [examDraft.paper_title, isLoading, isSubmitting, handleValidateExamRequest]);

  return (
    <div className="flex flex-col h-full w-full bg-gradient-to-b from-gray-900 to-gray-950 pb-16">
      {/* Header with logo and title */}
      <div className="pt-10 px-6 text-center mb-8">
        <div className="flex justify-center mb-3">
          <img
            src="/img/gptr-logo.png"
            alt="AI Exam"
            width={60}
            height={60}
            className="rounded-xl"
          />
        </div>
        <p className="text-gray-400 text-sm">这一页不再提交研究问题，而是提交结构化的组卷请求并调用后端验证。</p>
      </div>

      {/* Exam request form */}
      <div className="px-4 md:px-8 w-full max-w-lg mx-auto">
        <ExamRequestForm
          draft={examDraft}
          setDraft={setExamDraft}
          onSubmit={handleSubmit}
          disabled={isLoading || isSubmitting}
        />
      </div>

      {/* Recent research history */}
      {recentHistory.length > 0 && (
        <div className="mt-10 px-4">
          <h2 className="text-sm font-medium text-gray-400 mb-3 px-2">最近研究</h2>
          <div className="space-y-2">
            {recentHistory.map((item) => (
              <button
                key={item.id}
                onClick={() => handleHistoryItemClick(item.id)}
                className="w-full bg-gray-800/60 hover:bg-gray-800 rounded-lg p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-gray-600"
              >
                <h3 className="text-sm font-medium text-gray-200 line-clamp-1">{item.question}</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(item.timestamp || Date.now()).toLocaleString()}
                </p>
              </button>
            ))}
          </div>
          <div className="mt-3 text-center">
            <a
              href="/history"
              className="inline-block text-sm text-sky-400 hover:text-sky-300 transition-colors"
            >
              查看全部研究
            </a>
          </div>
        </div>
      )}

      {/* Features or tips section */}
      <div className="mt-auto pb-6 pt-8 px-4">
        <div className="bg-gray-800/40 border border-gray-700/50 rounded-xl p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-2">组卷提示</h3>
          <ul className="text-xs text-gray-400 space-y-1.5">
            <li className="flex items-start">
              <span className="text-sky-400 mr-1.5">•</span>
              <span>标题、学科、年级、题型和分值越明确，后端越容易校验通过</span>
            </li>
            <li className="flex items-start">
              <span className="text-sky-400 mr-1.5">•</span>
              <span>如果是纯题库模式，记得补充题库 ID 范围</span>
            </li>
            <li className="flex items-start">
              <span className="text-sky-400 mr-1.5">•</span>
              <span>如果总分或题量填不自洽，验证接口会直接返回结构性错误</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Styling for line clamp and input glow */}
      <style jsx global>{`
        .line-clamp-1 {
          overflow: hidden;
          display: -webkit-box;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 1;
        }
        
        .input-glow-subtle {
          box-shadow: 
            0 0 5px rgba(56, 189, 248, 0.2),
            0 0 12px rgba(14, 165, 233, 0.15),
            0 0 20px rgba(2, 132, 199, 0.1);
          animation: pulse-glow-subtle 3s infinite alternate;
        }
        
        @keyframes pulse-glow-subtle {
          0% {
            box-shadow: 
              0 0 5px rgba(56, 189, 248, 0.2),
              0 0 12px rgba(14, 165, 233, 0.15),
              0 0 20px rgba(2, 132, 199, 0.1);
          }
          100% {
            box-shadow: 
              0 0 8px rgba(56, 189, 248, 0.25),
              0 0 15px rgba(14, 165, 233, 0.2),
              0 0 25px rgba(2, 132, 199, 0.15);
          }
        }
        
        .input-glow-active {
          box-shadow: 
            0 0 5px rgba(56, 189, 248, 0.3),
            0 0 15px rgba(56, 189, 248, 0.3),
            0 0 25px rgba(14, 165, 233, 0.2),
            inset 0 0 3px rgba(186, 230, 253, 0.1);
          animation: pulse-glow-active 2s infinite alternate;
        }
        
        @keyframes pulse-glow-active {
          0% {
            box-shadow: 
              0 0 5px rgba(56, 189, 248, 0.3),
              0 0 15px rgba(56, 189, 248, 0.3),
              0 0 25px rgba(14, 165, 233, 0.2),
              inset 0 0 3px rgba(186, 230, 253, 0.1);
          }
          100% {
            box-shadow: 
              0 0 8px rgba(56, 189, 248, 0.4),
              0 0 20px rgba(14, 165, 233, 0.4),
              0 0 30px rgba(2, 132, 199, 0.3),
              inset 0 0 5px rgba(186, 230, 253, 0.2);
          }
        }
        
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
        
        .animate-spin {
          animation: spin 1s linear infinite;
        }
      `}</style>
    </div>
  );
} 
