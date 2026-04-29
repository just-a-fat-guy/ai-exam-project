import React, { useState, useRef, useEffect } from 'react';
import { ResearchHistoryItem } from '../types/data';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { motion, AnimatePresence } from 'framer-motion';

interface ResearchSidebarProps {
  history: ResearchHistoryItem[];
  onSelectResearch: (id: string) => void;
  onNewResearch: () => void;
  onDeleteResearch: (id: string) => void;
  isOpen: boolean;
  toggleSidebar: () => void;
  lockOpenOnDesktop?: boolean;
  currentConversationId?: string | null;
  generatingConversationId?: string | null;
  title?: string;
  newButtonLabel?: string;
  searchPlaceholder?: string;
  emptyTitle?: string;
  emptyDescription?: string;
}

const detectConversationMode = (item: ResearchHistoryItem) => {
  const hasExamArtifact = item.orderedData.some(
    (data) =>
      (data.type === "report" || data.type === "report_complete") &&
      (data.metadata as Record<string, unknown> | undefined)?.workflow_mode === "exam"
  );
  return hasExamArtifact ? "exam" : "research";
};

const buildConversationPreview = (item: ResearchHistoryItem) => {
  const lastChat = [...(item.chatMessages || [])].reverse().find((message) => message.role === "assistant");
  if (lastChat?.content?.trim()) {
    return lastChat.content.trim();
  }

  const reportItem = [...item.orderedData]
    .reverse()
    .find((data) => data.type === "report_complete" || data.type === "report");

  const reportOutput =
    (reportItem && "output" in reportItem && typeof reportItem.output === "string"
      ? reportItem.output
      : item.answer) || "";

  return reportOutput.replace(/^#+\s+/gm, "").replace(/\n+/g, " ").trim();
};

const ResearchSidebar: React.FC<ResearchSidebarProps> = ({
  history,
  onSelectResearch,
  onNewResearch,
  onDeleteResearch,
  isOpen,
  toggleSidebar,
  lockOpenOnDesktop = false,
  currentConversationId,
  generatingConversationId,
  title = "对话历史",
  newButtonLabel = "新对话",
  searchPlaceholder = "搜索对话记录",
  emptyTitle = "还没有对话历史",
  emptyDescription = "从一句教师需求开始，逐步生成并修改试卷。",
}) => {
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const sidebarRef = useRef<HTMLDivElement>(null);
  const effectiveOpen = lockOpenOnDesktop ? true : isOpen;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!lockOpenOnDesktop && effectiveOpen && 
          sidebarRef.current && 
          !sidebarRef.current.contains(event.target as Node)) {
        toggleSidebar();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [effectiveOpen, lockOpenOnDesktop, toggleSidebar]);

  // Format timestamp for display
  const formatTimestamp = (timestamp: number | string | Date | undefined) => {
    if (!timestamp) return '未知时间';
    
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return '未知时间';
      return formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
    } catch {
      return '未知时间';
    }
  };

  // Animation variants
  const sidebarVariants = {
    open: { 
      width: 'var(--sidebar-width)', 
      transition: { type: 'spring', stiffness: 250, damping: 25 } 
    },
    closed: { 
      width: 'var(--sidebar-min-width)', 
      transition: { type: 'spring', stiffness: 250, damping: 25, delay: 0.1 } 
    }
  };
  
  const fadeInVariants = {
    hidden: { opacity: 0, transition: { duration: 0.2 } },
    visible: { opacity: 1, transition: { duration: 0.3 } }
  };

  const filteredHistory = history.filter((item) => {
    const needle = searchQuery.trim().toLowerCase();
    if (!needle) return true;
    const preview = buildConversationPreview(item);
    return (
      item.question.toLowerCase().includes(needle) ||
      (item.answer || "").toLowerCase().includes(needle) ||
      preview.toLowerCase().includes(needle)
    );
  });

  const isRecentlyUpdated = (item: ResearchHistoryItem) => {
    const lastUpdated = Number(item.timestamp || (item as any).updated_at || (item as any).created_at || 0);
    return Number.isFinite(lastUpdated) && Date.now() - lastUpdated < 10 * 60 * 1000;
  };

  return (
    <>
      {/* Overlay for mobile */}
      <AnimatePresence>
        {effectiveOpen && !lockOpenOnDesktop && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="sidebar-overlay md:hidden fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm z-40" 
            onClick={toggleSidebar}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>
      
      <motion.div 
        ref={sidebarRef} 
        className="fixed top-0 left-0 h-full sidebar-z-index"
        variants={sidebarVariants}
        initial={false}
        animate={effectiveOpen ? 'open' : 'closed'}
        style={{
          '--sidebar-width': 'min(300px, 85vw)',
          '--sidebar-min-width': '12px'
        } as React.CSSProperties}
      >
        {/* Sidebar content */}
        <div 
          className={`h-full transition-all duration-300 text-white 
            ${effectiveOpen 
              ? 'apple-panel-strong overflow-hidden rounded-r-[32px] bg-black/45 p-3 sm:p-4 shadow-[0_24px_80px_rgba(0,0,0,0.42)]' 
              : 'overflow-visible bg-transparent p-0'
            }`}
        >
          {/* Toggle button - only shown when sidebar is closed */}
          <AnimatePresence mode="wait">
            {!effectiveOpen ? (
              <motion.div
                key="toggle-button"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute left-3 top-3 z-20 mx-auto flex h-10 w-10 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-white/8 bg-black/35 shadow-[0_16px_40px_rgba(0,0,0,0.34)] backdrop-blur-xl group"
                onClick={toggleSidebar}
                aria-label="Open sidebar"
              >
                <svg 
                  xmlns="http://www.w3.org/2000/svg" 
                  className="relative h-5 w-5 text-white/76 transition-transform duration-300 group-hover:scale-105" 
                  fill="none" 
                  viewBox="0 0 24 24" 
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </motion.div>
            ) : (
              <motion.div
                key="sidebar-content"
                initial="hidden"
                animate="visible"
                exit="hidden"
                variants={fadeInVariants}
              >
                <div className="flex justify-between items-center mb-5 sm:mb-6">
                  <h2 className="apple-heading-gradient text-lg font-semibold sm:text-xl">{title}</h2>
                  {!lockOpenOnDesktop ? (
                    <button
                      onClick={toggleSidebar}
                      className="apple-button-secondary flex h-9 w-9 items-center justify-center rounded-full sm:h-10 sm:w-10"
                      aria-label="Close sidebar"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 transition-transform duration-300 group-hover:scale-110" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                  ) : (
                    <div className="rounded-full border border-white/8 bg-white/[0.04] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-white/44">
                      固定
                    </div>
                  )}
                </div>

                {/* New Research button */}
                <button
                  onClick={onNewResearch}
                  className="apple-button-primary relative mb-5 w-full overflow-hidden rounded-[20px] px-4 py-3 text-sm font-semibold sm:mb-6"
                >
                  <div className="relative z-10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="mr-2 h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    {newButtonLabel}
                  </div>
                </button>

                <div className="mb-5 sm:mb-6">
                  <div className="apple-panel flex items-center gap-2 rounded-[18px] border-white/8 px-3 py-2.5">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white/34" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m21 21-4.35-4.35m1.85-5.15a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z" />
                    </svg>
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder={searchPlaceholder}
                      className="w-full bg-transparent text-sm text-white/82 outline-none placeholder:text-white/28"
                    />
                  </div>
                </div>

                {/* History list with improved scrollbar */}
                <div className="overflow-y-auto h-[calc(100vh-150px)] sm:h-[calc(100vh-190px)] pr-1 custom-scrollbar">
                  {filteredHistory.length === 0 ? (
                    <div className="text-center py-8 sm:py-10 px-4">
                        <div className="apple-panel mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full sm:h-20 sm:w-20">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 sm:h-10 w-8 sm:w-10 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                      <h3 className="mb-2 text-lg font-medium text-white/84">{emptyTitle}</h3>
                      <p className="text-sm text-white/44">{emptyDescription}</p>
                    </div>
                  ) : (
                    <ul className="space-y-2 sm:space-y-3">
                      {filteredHistory.map((item) => {
                        const mode = detectConversationMode(item);
                        const preview = buildConversationPreview(item);
                        const isActive = currentConversationId === item.id;
                        const isGenerating = generatingConversationId === item.id;
                        const recentlyUpdated = isRecentlyUpdated(item);
                        return (
                        <motion.li
                          key={item.id}
                          className={`apple-panel group relative overflow-hidden rounded-[24px] transition-all duration-300 hover:-translate-y-[1px] hover:border-white/14 hover:bg-white/[0.06] ${
                            isActive
                              ? "border-sky-400/28 bg-sky-400/[0.08] shadow-[0_18px_40px_rgba(56,189,248,0.12)]"
                              : "border-white/8"
                          }`}
                          onMouseEnter={() => setHoveredItem(item.id)}
                          onMouseLeave={() => setHoveredItem(null)}
                        >
                          <button
                            type="button"
                            className="relative block min-h-[56px] w-full pr-10 p-3 text-left sm:p-4"
                            onClick={(e) => {
                              e.preventDefault();
                              onSelectResearch(item.id);
                              if (!lockOpenOnDesktop) {
                                toggleSidebar();
                              }
                            }}
                          >
                            <div className="mb-2 flex items-center gap-2">
                              <span
                                className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] ${
                                  mode === "exam"
                                    ? "border-sky-400/18 bg-sky-400/[0.08] text-sky-100/70"
                                    : "border-white/10 bg-white/[0.05] text-white/52"
                                }`}
                              >
                                {mode === "exam" ? "AI组卷" : "研究"}
                              </span>
                              {isGenerating ? (
                                <span className="rounded-full border border-amber-400/20 bg-amber-400/[0.10] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] text-amber-100/80">
                                  生成中
                                </span>
                              ) : null}
                              {isActive ? (
                                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/[0.10] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] text-emerald-100/80">
                                  当前会话
                                </span>
                              ) : null}
                              {!isGenerating && recentlyUpdated ? (
                                <span className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white/56">
                                  最近修改
                                </span>
                              ) : null}
                            </div>
                            <h3 className={`truncate text-sm font-medium transition-colors duration-200 group-hover:text-white sm:text-base ${
                              isActive ? "text-white" : "text-white/84"
                            }`}>{item.question}</h3>
                            {preview ? (
                              <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-white/38">
                                {preview}
                              </p>
                            ) : null}
                            <p className="mt-1.5 flex items-center text-xs text-white/40">
                              <svg xmlns="http://www.w3.org/2000/svg" className="mr-1 h-3.5 w-3.5 text-white/28" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              {formatTimestamp(item.timestamp || (item as any).updated_at || (item as any).created_at)}
                            </p>
                          </button>
                          
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteResearch(item.id);
                            }}
                            className="apple-button-ghost absolute right-2 top-2 rounded-full p-1.5 opacity-0 transition-opacity group-hover:opacity-100"
                            aria-label="Delete research"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </motion.li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
      
      {/* Custom scrollbar styles */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.03);
          border-radius: 20px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(45, 212, 191, 0.3);
          border-radius: 20px;
          transition: all 0.3s;
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(45, 212, 191, 0.6);
        }
      `}</style>
    </>
  );
};

export default ResearchSidebar;
