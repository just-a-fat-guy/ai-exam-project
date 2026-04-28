import Image from "next/image";
import React from 'react';
import SourceCard from "./elements/SourceCard";

export default function Sources({
  sources,
  compact = false,
}: {
  sources: { name: string; url: string }[];
  compact?: boolean;
}) {
  if (compact) {
    // Compact version for chat responses
    return (
      <div className="max-h-[200px] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-300/10">
        <div className="flex w-full flex-wrap content-center items-center gap-2">
          {sources.map((source) => {
            // Extract domain from URL
            let displayUrl = source.url;
            try {
              const urlObj = new URL(source.url);
              displayUrl = urlObj.hostname.replace(/^www\./, '');
            } catch (e) {
              // If URL parsing fails, use the original URL
            }
            
            return (
              <a 
                key={source.url} 
                href={source.url} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs text-white/62 transition-colors hover:border-white/18 hover:bg-white/[0.08] hover:text-white"
                title={source.name}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
                {displayUrl}
              </a>
            );
          })}
        </div>
      </div>
    );
  }

  // Full version for research results
  return (
    <div className="container apple-panel h-auto w-full shrink-0 rounded-[30px] border-white/8 p-6">
      <div className="flex items-start gap-4 pb-4 lg:pb-4">
        <div className="apple-panel flex h-11 w-11 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
          <img src="/img/browser.svg" alt="sources" width={20} height={20} className="invert" />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            参考来源
          </div>
          <h3 className="text-sm font-medium text-white/84">
            {sources.length} 个来源
          </h3>
        </div>
      </div>
      <div className="apple-divider-line mb-5" />
      <div className="overflow-y-auto max-h-[250px] scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-300/10">
        <div className="flex w-full max-w-[890px] flex-wrap content-center items-center gap-[15px] pb-2">
          {sources.length > 0 ? (
            sources.map((source) => (
              <SourceCard source={source} key={source.url} />
            ))
          ) : (
            <>
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
              <div className="h-20 w-[260px] max-w-sm animate-pulse rounded-md bg-gray-300/20" />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
