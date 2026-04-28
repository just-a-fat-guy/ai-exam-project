import React from 'react';

interface HeaderProps {
  loading?: boolean;
  isStopped?: boolean;
  showResult?: boolean;
  onStop?: () => void;
  onNewResearch?: () => void;
  isCopilotMode?: boolean;
}

const Header = ({
  loading,
  isStopped,
  showResult,
  onStop,
  onNewResearch,
  isCopilotMode,
}: HeaderProps) => {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 px-4 pt-4 lg:px-8">
      <div className="mx-auto flex max-w-[1220px] items-center justify-between rounded-[28px] border border-white/10 bg-black/35 px-4 py-3 shadow-[0_20px_70px_rgba(0,0,0,0.38)] backdrop-blur-2xl lg:px-6">
        <a href="/" className="group flex items-center gap-3">
          <div className="apple-panel flex h-11 w-11 items-center justify-center rounded-2xl border-white/12 bg-white/[0.06] shadow-[0_12px_30px_rgba(0,0,0,0.28)]">
            <img
              src="/img/gptr-logo.png"
              alt="logo"
              width={30}
              height={30}
              className="transition-transform duration-300 group-hover:scale-105"
            />
          </div>
          <div className="hidden sm:block">
            <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-white/45">
              GPT Researcher
            </div>
            <div className="apple-heading-gradient text-lg font-semibold leading-none">
              单色研究系统
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

          {(isStopped || !loading) && showResult && !isCopilotMode && (
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
