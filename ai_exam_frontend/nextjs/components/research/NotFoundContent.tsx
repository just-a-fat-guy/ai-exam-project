import React from 'react';

interface NotFoundContentProps {
  onNewResearch: () => void;
}

export default function NotFoundContent({ onNewResearch }: NotFoundContentProps) {
  return (
    <div className="flex min-h-[100vh] flex-col items-center justify-center pt-[96px]">
      <div className="apple-panel-strong mx-auto max-w-md rounded-[32px] px-8 py-10 text-center">
        <div className="apple-panel mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="mb-2 text-2xl font-semibold text-white/88">没有找到这份研究</h2>
        <p className="mb-6 text-white/48">你访问的研究报告可能不存在，或者已经被删除。</p>
        <button 
          onClick={onNewResearch}
          className="apple-button-primary rounded-full px-5 py-2.5 text-sm font-medium"
        >
          返回首页
        </button>
      </div>
    </div>
  );
}
