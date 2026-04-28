import React, { useState } from 'react';
import { ResearchResults } from '@/components/ResearchResults';
import { Data, ChatBoxSettings } from '@/types/data';
import LoadingDots from '@/components/LoadingDots';
import Image from 'next/image';

interface ResearchPanelProps {
  orderedData: Data[];
  answer: string;
  allLogs: any[];
  chatBoxSettings: ChatBoxSettings;
  handleClickSuggestion: (value: string) => void;
  currentResearchId?: string;
  onShareClick?: () => void;
  isCopilotVisible?: boolean;
  setIsCopilotVisible?: React.Dispatch<React.SetStateAction<boolean>>;
  onNewResearch?: () => void;
  loading?: boolean;
  toggleSidebar?: () => void;
}

const ResearchPanel: React.FC<ResearchPanelProps> = ({
  orderedData,
  answer,
  allLogs,
  chatBoxSettings,
  handleClickSuggestion,
  currentResearchId,
  onShareClick,
  isCopilotVisible,
  setIsCopilotVisible,
  onNewResearch,
  loading,
  toggleSidebar
}) => {
  // Determine if research is complete (has answer) and copilot should be highlighted
  const researchComplete = Boolean(answer && answer.length > 0);
  const [isNotificationDismissed, setIsNotificationDismissed] = useState(false);
  
  return (
    <>
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-white/8 px-4 py-4">
        {/* Left side - Empty div to maintain flex layout */}
        <div className="flex items-center gap-3">
          <div className="apple-panel flex h-10 w-10 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
            <img
              src="/img/gptr-logo.png"
              alt="GPT Researcher"
              width={22}
              height={22}
              className="opacity-90"
            />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/34">
              研究视图
            </div>
            <div className="text-sm font-medium text-white/82">
              报告与来源
            </div>
          </div>
        </div>
        
        {/* Right side - Action buttons */}
        <div className="flex items-center gap-2">
          {/* New Research button */}
          {onNewResearch && (
            <button 
              onClick={onNewResearch}
              className="apple-button-primary flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              新建研究
            </button>
          )}
          
          {/* Share button */}
          {onShareClick && currentResearchId && (
            <button 
              onClick={onShareClick}
              className="apple-button-secondary flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                <polyline points="16 6 12 2 8 6"></polyline>
                <line x1="12" y1="2" x2="12" y2="15"></line>
              </svg>
              分享
            </button>
          )}
          
          {/* Show Copilot button - only visible when copilot is hidden */}
          {!isCopilotVisible && setIsCopilotVisible && (
            <button 
              onClick={() => setIsCopilotVisible(true)}
              className={`apple-button-secondary flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium ${researchComplete ? 'animate-chat-button-pulse' : ''}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              对话
            </button>
          )}
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-3 custom-scrollbar">
        {/* Filter out chat messages so they only show in the chat panel */}
        <div className="space-y-4 relative">          
          <ResearchResults
            orderedData={orderedData.filter(data => {
              // Keep everything except chat responses
              if (data.type === 'chat') return false;
              
              // For questions, only keep the first/initial question
              if (data.type === 'question') {
                return orderedData.indexOf(data) === 0;
              }
              
              // Keep all other types
              return true;
            })}
            answer={answer}
            allLogs={allLogs}
            chatBoxSettings={chatBoxSettings}
            handleClickSuggestion={handleClickSuggestion}
            currentResearchId={currentResearchId}
          />
          
          {/* Loading indicator - show during research */}
          {loading && (
            <div className="flex justify-center mt-6">
              <div className="apple-panel flex flex-col items-center rounded-[22px] px-6 py-5">
                <LoadingDots />
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Custom scrollbar styles */}
      <style jsx global>{`
        @keyframes chat-button-pulse {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.22);
            transform: scale(1);
          }
          70% {
            box-shadow: 0 0 0 12px rgba(255, 255, 255, 0);
            transform: scale(1.02);
          }
        }
        
        .animate-chat-button-pulse {
          animation: chat-button-pulse 2s infinite cubic-bezier(0.66, 0, 0, 1);
        }
        
        @keyframes fade-in-up {
          0% {
            opacity: 0;
            transform: translateY(10px);
          }
          100% {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        .animate-fade-in-up {
          animation: fade-in-up 0.6s ease-out forwards;
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
          background: rgba(255, 255, 255, 0.24);
        }
      `}</style>
    </>
  );
};

export default ResearchPanel; 
