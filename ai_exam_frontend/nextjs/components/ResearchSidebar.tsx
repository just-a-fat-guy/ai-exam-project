import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
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
}

const ResearchSidebar: React.FC<ResearchSidebarProps> = ({
  history,
  onSelectResearch,
  onNewResearch,
  onDeleteResearch,
  isOpen,
  toggleSidebar,
}) => {
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isOpen && 
          sidebarRef.current && 
          !sidebarRef.current.contains(event.target as Node)) {
        toggleSidebar();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, toggleSidebar]);

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

  return (
    <>
      {/* Overlay for mobile */}
      <AnimatePresence>
        {isOpen && (
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
        animate={isOpen ? 'open' : 'closed'}
        style={{
          '--sidebar-width': 'min(300px, 85vw)',
          '--sidebar-min-width': '12px'
        } as React.CSSProperties}
      >
        {/* Sidebar content */}
        <div 
          className={`h-full transition-all duration-300 text-white overflow-hidden 
            ${isOpen 
              ? 'apple-panel-strong rounded-r-[32px] bg-black/45 p-3 sm:p-4 shadow-[0_24px_80px_rgba(0,0,0,0.42)]' 
              : 'bg-transparent p-0'
            }`}
        >
          {/* Toggle button - only shown when sidebar is closed */}
          <AnimatePresence mode="wait">
            {!isOpen ? (
              <motion.div
                key="toggle-button"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute left-4 top-3 z-10 mx-auto flex h-10 w-10 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-white/8 bg-black/35 shadow-[0_16px_40px_rgba(0,0,0,0.34)] backdrop-blur-xl group"
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
                  <h2 className="apple-heading-gradient text-lg font-semibold sm:text-xl">研究历史</h2>
                  <button
                    onClick={toggleSidebar}
                    className="apple-button-secondary flex h-9 w-9 items-center justify-center rounded-full sm:h-10 sm:w-10"
                    aria-label="Close sidebar"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 transition-transform duration-300 group-hover:scale-110" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                  </button>
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
                    新建研究
                  </div>
                </button>

                {/* History list with improved scrollbar */}
                <div className="overflow-y-auto h-[calc(100vh-150px)] sm:h-[calc(100vh-190px)] pr-1 custom-scrollbar">
                  {history.length === 0 ? (
                    <div className="text-center py-8 sm:py-10 px-4">
                        <div className="apple-panel mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full sm:h-20 sm:w-20">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 sm:h-10 w-8 sm:w-10 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                      <h3 className="mb-2 text-lg font-medium text-white/84">还没有研究历史</h3>
                      <p className="text-sm text-white/44">开始你的第一次研究，逐步建立自己的知识资料库</p>
                    </div>
                  ) : (
                    <ul className="space-y-2 sm:space-y-3">
                      {history.map((item) => (
                        <motion.li 
                          key={item.id}
                          className="apple-panel group relative overflow-hidden rounded-[24px] border-white/8 transition-all duration-300 hover:-translate-y-[1px] hover:border-white/14 hover:bg-white/[0.06]"
                          onMouseEnter={() => setHoveredItem(item.id)}
                          onMouseLeave={() => setHoveredItem(null)}
                        >
                          
                          <Link
                            href={`/research/${item.id}`}
                            className="relative block min-h-[56px] w-full pr-10 p-3 text-left sm:p-4"
                            onClick={(e) => {
                              // Only prevent default if we're just closing the sidebar
                              if (!isOpen) {
                                e.preventDefault();
                              }
                              // Call onSelectResearch only if we're actually navigating
                              if (isOpen) {
                                onSelectResearch(item.id);
                              }
                              // Always close the sidebar
                              toggleSidebar();
                            }}
                          >
                            <h3 className="truncate text-sm font-medium text-white/84 transition-colors duration-200 group-hover:text-white sm:text-base">{item.question}</h3>
                            <p className="mt-1.5 flex items-center text-xs text-white/40">
                              <svg xmlns="http://www.w3.org/2000/svg" className="mr-1 h-3.5 w-3.5 text-white/28" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              {formatTimestamp(item.timestamp || (item as any).updated_at || (item as any).created_at)}
                            </p>
                          </Link>
                          
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
                      ))}
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
