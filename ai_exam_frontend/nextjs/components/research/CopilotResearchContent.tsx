import { useRef, Dispatch, SetStateAction, useState, useCallback, useEffect } from "react";
import ResearchPanel from "@/components/research/ResearchPanel";
import CopilotPanel from "@/components/research/CopilotPanel";
import { ChatBoxSettings, Data } from "@/types/data";
import { ExamDraftData } from "@/types/exam";

interface CopilotResearchContentProps {
  orderedData: Data[];
  answer: string;
  allLogs: any[];
  chatBoxSettings: ChatBoxSettings;
  loading: boolean;
  isStopped: boolean;
  promptValue: string;
  chatPromptValue: string;
  setPromptValue: Dispatch<SetStateAction<string>>;
  setChatPromptValue: Dispatch<SetStateAction<string>>;
  handleDisplayResult: (question: string) => void;
  handleChat: (message: string) => void;
  handleClickSuggestion: (value: string) => void;
  currentResearchId?: string;
  onShareClick?: () => void;
  reset?: () => void;
  isProcessingChat?: boolean;
  onNewResearch?: () => void;
  toggleSidebar?: () => void;
  examPaper?: ExamDraftData | null;
  reviewingQuestionIds?: string[];
  onReviewExamQuestion?: (
    questionId: string,
    action: "approve" | "reject" | "request_regeneration",
    comment?: string
  ) => Promise<boolean>;
}

export default function CopilotResearchContent({
  orderedData,
  answer,
  allLogs,
  chatBoxSettings,
  loading,
  isStopped,
  promptValue,
  chatPromptValue,
  setPromptValue,
  setChatPromptValue,
  handleDisplayResult,
  handleChat,
  handleClickSuggestion,
  currentResearchId,
  onShareClick,
  reset,
  isProcessingChat = false,
  onNewResearch,
  toggleSidebar,
  examPaper,
  reviewingQuestionIds = [],
  onReviewExamQuestion,
}: CopilotResearchContentProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isExamWorkflow = (chatBoxSettings.workflow_mode || "exam") === "exam";
  // Initialize copilot as hidden when loading
  const [isCopilotVisible, setIsCopilotVisible] = useState(false);
  const [showAnimation, setShowAnimation] = useState(false);
  // Track if user manually closed the copilot panel
  const [userClosedCopilot, setUserClosedCopilot] = useState(false);
  // State for split pane resizing
  const [resizingActive, setResizingActive] = useState(false);
  const [researchPanelWidth, setResearchPanelWidth] = useState(58); // percentage
  const [isMobile, setIsMobile] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const widthRef = useRef(researchPanelWidth);
  const researchPanelRef = useRef<HTMLDivElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const lastUpdateTimeRef = useRef(0);
  
  // Check if we're on mobile
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    
    // Initial check
    checkIfMobile();
    
    // Add event listener for window resize
    window.addEventListener('resize', checkIfMobile);
    
    // Cleanup
    return () => window.removeEventListener('resize', checkIfMobile);
  }, []);
  
  // Create a memoized toggle function that's compatible with Dispatch<SetStateAction<boolean>>
  const toggleCopilotVisibility: Dispatch<SetStateAction<boolean>> = useCallback((value) => {
    // Handle both function and direct value cases
    const newValue = typeof value === 'function' ? value(isCopilotVisible) : value;
    
    // Set state without triggering scroll
    setIsCopilotVisible(newValue);
    
    // Track user's explicit action of closing the panel
    if (newValue === false) {
      setUserClosedCopilot(true);
    }
    
    // If we're showing the copilot, trigger the animation
    if (newValue && !isCopilotVisible) {
      setShowAnimation(true);
    }
    
    // Prevent scroll jumping by keeping current scroll position
    const currentScrollY = window.scrollY;
    
    // Use requestAnimationFrame to restore scroll position after the state update
    requestAnimationFrame(() => {
      window.scrollTo({
        top: currentScrollY,
        behavior: 'auto'
      });
    });
  }, [isCopilotVisible]);
  
  // Effect to handle initial state and research completion
  useEffect(() => {
    // Reset userClosedCopilot when new research starts
    if (loading) {
      setUserClosedCopilot(false);
    }
    
    // Automatically open the copilot when research completes BUT only if user hasn't manually closed it
    if (!isExamWorkflow && !loading && answer && !isCopilotVisible && !userClosedCopilot) {
      // Add a slight delay before showing the copilot for a better UX
      const timer = setTimeout(() => {
        setIsCopilotVisible(true);
        setShowAnimation(true);
      }, 800);
      
      return () => clearTimeout(timer);
    }
  }, [loading, answer, isCopilotVisible, userClosedCopilot, isExamWorkflow]);
  
  // Extract the initial question from orderedData
  const initialQuestion = orderedData.find(data => data.type === 'question');
  const questionText = initialQuestion?.content || '';

  // Handle resize start
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setResizingActive(true);
  }, []);

  // Handle resize move
  useEffect(() => {
    const handleResizeMove = (e: MouseEvent) => {
      if (!resizingActive || !containerRef.current) return;
      
      // Throttle updates to every 16ms (approx 60fps)
      const now = Date.now();
      if (now - lastUpdateTimeRef.current < 16) {
        return;
      }
      lastUpdateTimeRef.current = now;
      
      // Use requestAnimationFrame for smoother updates
      requestAnimationFrame(() => {
        if (!containerRef.current) return;
        
        const containerRect = containerRef.current.getBoundingClientRect();
        const containerWidth = containerRect.width;
        const mouseX = e.clientX - containerRect.left;
        
        // Calculate percentage width (with constraints)
        let newWidth = (mouseX / containerWidth) * 100;
        newWidth = Math.max(30, Math.min(70, newWidth)); // Constrain between 30% and 70%
        
        // Store width in ref without causing re-renders
        widthRef.current = newWidth;
        
        // Apply directly to DOM elements using refs
        if (researchPanelRef.current) {
          researchPanelRef.current.style.width = `${newWidth}%`;
        }
        if (chatPanelRef.current) {
          chatPanelRef.current.style.width = `${100 - newWidth}%`;
        }
      });
    };

    const handleResizeEnd = () => {
      // Only update state once dragging ends
      setResearchPanelWidth(widthRef.current);
      setResizingActive(false);
    };

    if (resizingActive) {
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
    }

    return () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
    };
  }, [resizingActive]);

  return (
    <div 
      ref={containerRef}
      className="relative flex h-screen w-full flex-col gap-3 px-4 pb-4 lg:flex-row lg:px-8"
    >
      <div className="pointer-events-none absolute inset-0 rounded-[36px] border border-white/6" />
      
      {/* Research Results Panel (Left) */}
      <div 
        ref={researchPanelRef}
        data-panel="task"
        className={`apple-panel-strong w-full ${isCopilotVisible && !isExamWorkflow ? '' : 'lg:w-full'} h-full overflow-hidden flex flex-col rounded-[30px] border-white/8 bg-white/[0.035] ${!resizingActive ? 'transition-width duration-300' : ''}`}
        style={isCopilotVisible && !isMobile && !isExamWorkflow ? { width: `${researchPanelWidth}%` } : {}}
      >
        <ResearchPanel 
          orderedData={orderedData}
          answer={answer}
          allLogs={allLogs}
          chatBoxSettings={chatBoxSettings}
          handleClickSuggestion={handleClickSuggestion}
          currentResearchId={currentResearchId}
          onShareClick={onShareClick}
          isCopilotVisible={isCopilotVisible}
          setIsCopilotVisible={toggleCopilotVisibility}
          onNewResearch={onNewResearch}
          loading={loading}
          toggleSidebar={toggleSidebar}
          examPaper={examPaper}
          reviewingQuestionIds={reviewingQuestionIds}
          onReviewExamQuestion={onReviewExamQuestion}
        />
      </div>

      {/* Resizer handle */}
      {!isExamWorkflow && isCopilotVisible && (
        <div
          className={`hidden lg:flex flex-col items-center justify-center w-3 h-full cursor-col-resize transition-colors duration-150 z-10 ${resizingActive ? 'bg-white/10' : 'bg-transparent hover:bg-white/6'}`}
          onMouseDown={handleResizeStart}
        >
          <div className="flex flex-col items-center justify-center">
            <div className="h-20 w-px rounded-full bg-gradient-to-b from-transparent via-white/35 to-transparent"></div>
          </div>
        </div>
      )}
      
      {/* Copilot Chat Panel (Right) */}
      {!isExamWorkflow && isCopilotVisible && (
        <div 
          ref={chatPanelRef}
          data-panel="chat"
          className={`apple-panel-strong w-full h-1/2 lg:h-full overflow-hidden flex flex-col rounded-[30px] border-white/8 bg-white/[0.035] ${!resizingActive ? 'transition-width duration-300' : ''} ${
            showAnimation ? 'animate-copilot-entrance' : ''
          }`}
          style={!isMobile ? { width: `${100 - researchPanelWidth}%` } : {}}
        >
          <CopilotPanel
            question={questionText}
            chatPromptValue={chatPromptValue}
            setChatPromptValue={setChatPromptValue}
            handleChat={handleChat}
            orderedData={orderedData}
            loading={loading}
            isProcessingChat={isProcessingChat}
            isStopped={isStopped}
            bottomRef={bottomRef}
            isCopilotVisible={isCopilotVisible}
            setIsCopilotVisible={toggleCopilotVisibility}
          />
        </div>
      )}
      
      {/* Custom styles for animations */}
      <style jsx global>{`
        @keyframes subtle-pulse {
          0% { opacity: 0.8; }
          50% { opacity: 1; }
          100% { opacity: 0.8; }
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        @keyframes spin-slow {
          to { transform: rotate(-360deg); }
        }
        
        @keyframes spin-slower {
          to { transform: rotate(360deg); }
        }
        
        .animate-spin {
          animation: spin 1.5s linear infinite;
        }
        
        .animate-spin-slow {
          animation: spin-slow 3s linear infinite;
        }
        
        .animate-spin-slower {
          animation: spin-slower 4.5s linear infinite;
        }
        
        @keyframes copilot-entrance {
          0% { 
            opacity: 0; 
            transform: translateX(40px) scale(0.95);
            box-shadow: 0 0 0 rgba(17, 24, 39, 0);
          }
          70% {
            opacity: 1;
            transform: translateX(-5px) scale(1.02);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
          }
          100% { 
            opacity: 1; 
            transform: translateX(0) scale(1);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
          }
        }
        
        .animate-copilot-entrance {
          animation: copilot-entrance 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
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

        .transition-width {
          transition: width 0.3s ease;
        }
      `}</style>
    </div>
  );
} 
