import React, { useRef, useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { ChatBoxSettings } from "@/types/data";
import Image from "next/image";

interface CopilotLayoutProps {
  children: React.ReactNode;
  loading: boolean;
  isStopped: boolean;
  showResult: boolean;
  onStop?: () => void;
  onNewResearch?: () => void;
  chatBoxSettings: ChatBoxSettings;
  setChatBoxSettings: React.Dispatch<React.SetStateAction<ChatBoxSettings>>;
  mainContentRef?: React.RefObject<HTMLDivElement>;
  toastOptions?: Record<string, any>;
  toggleSidebar?: () => void;
  hideResultAction?: boolean;
  shiftHeaderForSidebar?: boolean;
}

export default function CopilotLayout({
  children,
  loading,
  isStopped,
  showResult,
  onStop,
  onNewResearch,
  chatBoxSettings,
  setChatBoxSettings,
  mainContentRef,
  toastOptions = {},
  toggleSidebar,
  hideResultAction = false,
  shiftHeaderForSidebar = false,
}: CopilotLayoutProps) {
  const defaultRef = useRef<HTMLDivElement>(null);
  const contentRef = mainContentRef || defaultRef;
  const lockViewport = hideResultAction && showResult;
  
  return (
    <main className={`relative flex flex-col overflow-hidden text-white ${lockViewport ? "h-screen" : "min-h-screen"}`}>
      <Toaster 
        position="bottom-center" 
        toastOptions={toastOptions}
      />

      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="apple-noise absolute inset-0" />
        <div className="absolute left-[8%] top-[12%] h-[26rem] w-[26rem] rounded-full bg-white/7 blur-[110px] apple-ambient" />
        <div className="absolute right-[8%] top-[28%] h-[22rem] w-[22rem] rounded-full bg-zinc-300/10 blur-[110px] apple-ambient" />
        <div className="absolute bottom-[-8rem] left-1/2 h-[20rem] w-[48rem] -translate-x-1/2 rounded-full bg-white/6 blur-[120px] apple-ambient" />
      </div>
      
      {/* Show Header only when not in research mode */}
      {!showResult && (
        <Header 
          loading={loading}
          isStopped={isStopped}
          showResult={showResult}
          onStop={onStop || (() => {})}
          onNewResearch={onNewResearch}
          isCopilotMode={true}
          hideResultAction={hideResultAction}
          shiftForSidebar={shiftHeaderForSidebar}
        />
      )}
      
      <div 
        ref={contentRef}
        className={`relative z-10 flex flex-1 flex-col ${
          lockViewport
            ? "h-screen overflow-hidden pt-[96px]"
            : !showResult
              ? "pt-[120px]"
              : "pt-[96px]"
        }`}
      >
        {children}
      </div>
      
      {!lockViewport ? (
        <div className="relative z-10 px-4 pb-4 lg:px-8">
          <Footer setChatBoxSettings={setChatBoxSettings} chatBoxSettings={chatBoxSettings} />
        </div>
      ) : null}
    </main>
  );
} 
