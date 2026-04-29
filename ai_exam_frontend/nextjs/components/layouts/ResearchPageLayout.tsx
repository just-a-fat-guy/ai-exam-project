import { ReactNode, useRef, useCallback, useEffect, Dispatch, SetStateAction } from "react";
import { Toaster } from "react-hot-toast";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { ChatBoxSettings } from "@/types/data";

interface ResearchPageLayoutProps {
  children: ReactNode;
  loading: boolean;
  isStopped: boolean;
  showResult: boolean;
  onStop?: () => void;
  onNewResearch: () => void;
  chatBoxSettings: ChatBoxSettings;
  setChatBoxSettings: Dispatch<SetStateAction<ChatBoxSettings>>;
  mainContentRef?: React.RefObject<HTMLDivElement>;
  showScrollButton?: boolean;
  onScrollToBottom?: () => void;
  toastOptions?: object;
  hideResultAction?: boolean;
  lockViewport?: boolean;
  shiftHeaderForSidebar?: boolean;
}

export default function ResearchPageLayout({
  children,
  loading,
  isStopped,
  showResult,
  onStop,
  onNewResearch,
  chatBoxSettings,
  setChatBoxSettings,
  mainContentRef,
  showScrollButton = false,
  onScrollToBottom,
  toastOptions = {},
  hideResultAction = false,
  lockViewport = false,
  shiftHeaderForSidebar = false,
}: ResearchPageLayoutProps) {
  const defaultRef = useRef<HTMLDivElement>(null);
  const contentRef = mainContentRef || defaultRef;
  const shouldLockViewport = lockViewport || (hideResultAction && showResult);

  return (
    <main className={`relative flex flex-col overflow-hidden text-white ${shouldLockViewport ? "h-screen" : "min-h-screen"}`}>
      <Toaster 
        position="bottom-center" 
        toastOptions={toastOptions}
      />

      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="apple-noise absolute inset-0" />
        <div className="absolute left-[10%] top-[15%] h-[24rem] w-[24rem] rounded-full bg-white/7 blur-[110px] apple-ambient" />
        <div className="absolute right-[6%] top-[30%] h-[18rem] w-[18rem] rounded-full bg-zinc-300/10 blur-[100px] apple-ambient" />
        <div className="absolute bottom-[-7rem] left-1/2 h-[22rem] w-[50rem] -translate-x-1/2 rounded-full bg-white/6 blur-[120px] apple-ambient" />
      </div>
      
      <Header 
        loading={loading}
        isStopped={isStopped}
        showResult={showResult}
        onStop={onStop || (() => {})}
        onNewResearch={onNewResearch}
        hideResultAction={hideResultAction}
        shiftForSidebar={shiftHeaderForSidebar}
      />
      
      <div 
        ref={contentRef}
        className={`relative z-10 ${shouldLockViewport ? "h-screen overflow-hidden pt-[104px]" : "min-h-[100vh] pt-[104px]"}`}
      >
        {children}
      </div>
      
      {showScrollButton && showResult && (
        <button
          onClick={onScrollToBottom}
          className="apple-button-secondary fixed bottom-8 right-8 z-50 flex h-12 w-12 items-center justify-center rounded-full text-white backdrop-blur-xl"
        >
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className="h-6 w-6" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M19 14l-7 7m0 0l-7-7m7 7V3" 
            />
          </svg>
        </button>
      )}
      
      {!shouldLockViewport ? (
        <div className="relative z-10 px-4 pb-4 lg:px-8">
          <Footer setChatBoxSettings={setChatBoxSettings} chatBoxSettings={chatBoxSettings} />
        </div>
      ) : null}
    </main>
  );
}
