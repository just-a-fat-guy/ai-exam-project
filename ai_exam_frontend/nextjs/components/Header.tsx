import React from 'react';

interface HeaderProps {
  loading?: boolean;
  isStopped?: boolean;
  showResult?: boolean;
  onStop?: () => void;
  onNewResearch?: () => void;
  isCopilotMode?: boolean;
  hideResultAction?: boolean;
  shiftForSidebar?: boolean;
}

const Header = ({
  loading,
  isStopped,
  showResult,
  onStop,
  onNewResearch,
  isCopilotMode,
  hideResultAction,
  shiftForSidebar = false,
}: HeaderProps) => {
  return (
    <div
      className={`fixed top-0 right-0 z-40 px-4 pt-4 transition-[left,padding] duration-300 lg:px-6 ${
        shiftForSidebar ? "left-0 md:left-[320px]" : "left-0"
      }`}
    >
      <div className="mx-auto flex max-w-[1240px] items-center justify-between rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.025))] px-4 py-3 shadow-[0_18px_56px_rgba(0,0,0,0.28)] backdrop-blur-xl lg:px-5">
        <a href="/" className="group flex items-center gap-3">
          <div className="apple-panel flex h-10 w-10 items-center justify-center rounded-2xl border-white/10 bg-white/[0.055] shadow-[0_10px_26px_rgba(0,0,0,0.24)]">
            <img
              src="/img/ai-exam-icon.svg"
              alt="logo"
              width={26}
              height={26}
              className="transition-transform duration-300 group-hover:scale-105"
            />
          </div>
          <div className="hidden sm:block">
            <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-white/45">
              AI Exam
            </div>
            <div className="apple-heading-gradient text-base font-semibold leading-none lg:text-[17px]">
              AI 智能组卷系统
            </div>
          </div>
        </a>

        <div className="flex items-center gap-2">
          {showResult && (
            <div className="hidden items-center gap-2 rounded-full border border-white/8 bg-white/[0.04] px-3 py-1.5 text-xs text-white/60 sm:flex">
              <span
                className={`h-2 w-2 rounded-full ${
                  loading && !isStopped ? 'bg-white animate-pulse' : 'bg-white/40'
                }`}
              />
              <span>{loading && !isStopped ? '研究进行中' : '已就绪'}</span>
            </div>
          )}

          {loading && !isStopped && (
            <button
              onClick={onStop}
              className="apple-button-secondary flex h-11 items-center justify-center rounded-full px-4 text-sm font-medium whitespace-nowrap"
            >
              停止
            </button>
          )}

          {(isStopped || !loading) && showResult && !isCopilotMode && !hideResultAction && (
            <button
              onClick={onNewResearch}
              className="apple-button-primary flex h-11 items-center justify-center rounded-full px-5 text-sm font-medium whitespace-nowrap"
            >
              发起新研究
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Header;
