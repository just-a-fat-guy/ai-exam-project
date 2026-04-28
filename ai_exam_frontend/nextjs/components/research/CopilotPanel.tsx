import React, { Dispatch, SetStateAction, useEffect, useRef } from 'react';
import ChatInput from '@/components/ResearchBlocks/elements/ChatInput';
import LoadingDots from '@/components/LoadingDots';
import { Data } from '@/types/data';
import Question from '@/components/ResearchBlocks/Question';
import ChatResponse from '@/components/ResearchBlocks/ChatResponse';
import Image from 'next/image';

interface CopilotPanelProps {
  question: string;
  chatPromptValue: string;
  setChatPromptValue: Dispatch<SetStateAction<string>>;
  handleChat: (message: string) => void;
  orderedData: Data[];
  loading: boolean;
  isProcessingChat: boolean;
  isStopped: boolean;
  bottomRef: React.RefObject<HTMLDivElement>;
  isCopilotVisible?: boolean;
  setIsCopilotVisible?: Dispatch<SetStateAction<boolean>>;
}

const CopilotPanel: React.FC<CopilotPanelProps> = ({
  question,
  chatPromptValue,
  setChatPromptValue,
  handleChat,
  orderedData,
  loading,
  isProcessingChat,
  isStopped,
  bottomRef,
  isCopilotVisible,
  setIsCopilotVisible
}) => {
  // Filter to only get chat messages (questions and responses) after the initial question
  const chatMessages = orderedData.filter((data, index) => {
    // Include all questions except the first one
    if (data.type === 'question') {
      return index > 0;
    }
    // Include all chat responses
    return data.type === 'chat';
  });

  // Reference to the chat container
  const chatContainerRef = useRef<HTMLDivElement>(null);
  
  // Function to scroll to bottom
  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  };

  // Scroll when messages change or loading/processing state changes
  useEffect(() => {
    scrollToBottom();
  }, [chatMessages.length, loading, isProcessingChat]);

  // Also handle mutations in the DOM that might affect scroll height
  useEffect(() => {
    if (!chatContainerRef.current) return;
    
    const observer = new MutationObserver(scrollToBottom);
    
    observer.observe(chatContainerRef.current, {
      childList: true,
      subtree: true,
      characterData: true
    });
    
    return () => observer.disconnect();
  }, []);

  return (
    <>
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-white/8 px-4 py-4">
        {/* Left side */}
        <div className="flex items-center">
          <div className="apple-panel flex h-10 w-10 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
            <img
              src="/img/gptr-logo.png"
              alt="logo"
              width={22}
              height={22}
              className="opacity-90"
            />
          </div>
          <div className="ml-3">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/34">
              助手面板
            </div>
            <h2 className="text-sm font-medium text-white/84">
              GPT Researcher 助手
            </h2>
          </div>
        </div>
        
        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Connection status indicator */}
          <div className="flex items-center">
            <div className={`mr-2 h-1.5 w-1.5 rounded-full ${loading || isProcessingChat ? 'bg-white animate-pulse' : 'bg-white/50'}`}></div>
            <span className="text-xs text-white/46">{loading ? '研究中' : isProcessingChat ? '思考中' : '在线'}</span>
          </div>
          
          {/* Toggle button */}
          {setIsCopilotVisible && (
            <button 
              onClick={(e) => {
                e.preventDefault();
                setIsCopilotVisible(false);
              }}
              className="apple-button-ghost flex h-8 w-8 items-center justify-center rounded-full"
              aria-label="Hide copilot panel"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Chat Messages - Scrollable */}
      <div 
        ref={chatContainerRef} 
        className="flex-1 overflow-y-auto px-4 py-4 custom-scrollbar"
      >
        {/* Status message - conditional on research state */}
        <div className="mb-4">
          <div className="apple-panel rounded-[24px] px-4 py-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-white/72">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <div className="text-sm text-white/68">
                {loading ? (
                  <p>正在处理你的研究任务，等结果整理完成后我会继续帮你分析。</p>
                ) : (
                  <p>我已经读取并整理了这次研究结果。你可以继续追问，我会基于报告内容回答。</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Chat messages */}
        <div className="space-y-4">
          {chatMessages.map((data, index) => {
            if (data.type === 'question') {
              return (
                <div key={`chat-question-${index}`}>
                  <Question question={data.content} />
                </div>
              );
            } else if (data.type === 'chat') {
              return (
                <div key={`chat-answer-${index}`}>
                  <ChatResponse answer={data.content} metadata={data.metadata} />
                </div>
              );
            }
            return null;
          })}
        </div>

        {/* Loading indicator - always show during research or processing */}
        {(loading || isProcessingChat) && (
          <div className="flex justify-center">
            <div className="flex flex-col items-center">
              <LoadingDots />
            </div>
          </div>
        )}

        {/* Invisible element for scrolling */}
        <div ref={bottomRef} />
      </div>

      {/* Chat Input */}
      <div className="border-t border-white/8 px-4 py-4">
        {!isStopped && (
          <ChatInput
            promptValue={chatPromptValue}
            setPromptValue={setChatPromptValue}
            handleSubmit={handleChat}
            disabled={loading || isProcessingChat}
          />
        )}
        {isStopped && (
          <div className="apple-panel rounded-[22px] p-3 text-center text-sm text-white/52">
            当前研究已停止。请先发起新的研究任务，再继续对话。
          </div>
        )}
      </div>

      {/* Custom scrollbar styles */}
      <style jsx global>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        
        .animate-pulse {
          animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.03);
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.16);
          border-radius: 20px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.22);
        }
      `}</style>
    </>
  );
};

export default CopilotPanel; 
