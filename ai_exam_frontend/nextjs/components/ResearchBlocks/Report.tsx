import Image from "next/image";
import React, { useState, useEffect } from 'react';
import { toast } from "react-hot-toast";
import { markdownToHtml } from '../../helpers/markdownHelper';
import '../../styles/markdown.css';
import { useResearchHistoryContext } from '../../hooks/ResearchHistoryContext';
import { ChatMessage } from '../../types/data';

export default function Report({ answer, researchId }: { answer: string, researchId?: string }) {
    const [htmlContent, setHtmlContent] = useState('');
    const { getChatMessages } = useResearchHistoryContext();
    // Memoize this value to prevent re-renders
    const chatMessages = researchId ? getChatMessages(researchId) : [];

    useEffect(() => {
      if (answer) {
        markdownToHtml(answer).then((html) => setHtmlContent(html));
      }
    }, [answer]);
    
    return (
      <div className="container apple-panel-strong flex h-auto w-full shrink-0 gap-4 rounded-[32px] border-white/8 p-6 shadow-[0_24px_70px_rgba(0,0,0,0.32)]">
        <div className="w-full">
          <div className="flex items-center justify-between pb-4">
            <div className="flex items-center gap-3">
              <div className="apple-panel flex h-11 w-11 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
                <svg 
                  xmlns="http://www.w3.org/2000/svg" 
                  viewBox="0 0 24 24" 
                  width={18}
                  height={18}
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth={1.5} 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  className="text-white/78"
                >
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
                  最终输出
                </div>
                <h3 className="text-sm font-medium text-white/84">研究报告</h3>
              </div>
            </div>
            {answer && (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(answer.trim());
                    toast("报告已复制到剪贴板", {
                      icon: "✂️",
                    });
                  }}
                  className="apple-button-secondary rounded-full p-2 transition-opacity duration-200"
                >
                  <img
                    src="/img/copy-white.svg"
                    alt="copy"
                    width={20}
                    height={20}
                    className="cursor-pointer invert"
                  />
                </button>
              </div>
            )}
          </div>
          
          <div className="apple-divider-line mb-5" />
          <div className="flex flex-wrap content-center items-center gap-[15px] px-2 sm:px-4">
            <div className="log-message w-full whitespace-pre-wrap text-base font-light leading-[1.75] text-white/82">
              {answer ? (
                <div className="markdown-content prose prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: htmlContent }} />
              ) : (
                <div className="flex w-full flex-col gap-2">
                  <div className="h-6 w-full animate-pulse rounded-md bg-gray-300/20" />
                  <div className="h-6 w-[85%] animate-pulse rounded-md bg-gray-300/20" />
                  <div className="h-6 w-[90%] animate-pulse rounded-md bg-gray-300/20" />
                  <div className="h-6 w-[70%] animate-pulse rounded-md bg-gray-300/20" />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
} 
