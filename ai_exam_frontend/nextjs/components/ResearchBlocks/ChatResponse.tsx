import React, { useState, useEffect } from 'react';
import { toast } from "react-hot-toast";
import { markdownToHtml } from '../../helpers/markdownHelper';
import '../../styles/markdown.css';
import Sources from './Sources';

interface ChatResponseProps {
  answer: string;
  metadata?: {
    tool_calls?: Array<{
      tool: string;
      query: string;
      search_metadata: {
        query: string;
        sources: Array<{
          title: string;
          url: string;
          content: string;
        }>
      }
    }>
  }
}

export default function ChatResponse({ answer, metadata }: ChatResponseProps) {
    const [htmlContent, setHtmlContent] = useState('');
    
    // Check if we have sources from a web search tool call
    const hasWebSources = metadata?.tool_calls?.some(
      tool => tool.tool === 'quick_search' && tool.search_metadata?.sources?.length > 0
    );
    
    // Get all sources from web searches
    const webSources = metadata?.tool_calls
      ?.filter(tool => tool.tool === 'quick_search')
      .flatMap(tool => tool.search_metadata?.sources || [])
      .map(source => ({
        name: source.title,
        url: source.url
      })) || [];

    useEffect(() => {
      if (answer) {
        markdownToHtml(answer).then((html) => setHtmlContent(html));
      }
    }, [answer]);
    
    // Format the answer for display
    const formattedAnswer = answer.trim() || '暂无回答内容。';
    
    const copyToClipboard = () => {
        // Copy the plain text of the answer instead of the HTML
        navigator.clipboard.writeText(formattedAnswer)
            .then(() => {
                toast.success('已复制到剪贴板');
            })
            .catch((err) => {
                console.error('Failed to copy: ', err);
                toast.error('复制到剪贴板失败');
            });
    };
  
    return (
      <div className="container apple-panel flex h-auto w-full shrink-0 gap-4 rounded-[28px] border-white/8 p-5">
        <div className="w-full">
          <div className="flex items-center justify-between pb-3">
            <div className="flex items-center gap-3">
              <div className="apple-panel flex h-10 w-10 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
                  追问回答
                </div>
                <h3 className="text-sm font-medium text-white/84">回答</h3>
              </div>
            </div>
            <button 
              onClick={copyToClipboard}
              className="apple-button-secondary rounded-full p-2 transition-opacity duration-200"
              aria-label="复制到剪贴板"
              title="复制到剪贴板"
            >
              <img
                src="/img/copy-white.svg"
                alt="copy"
                width={20}
                height={20}
                className="cursor-pointer invert"
              />
            </button>
          </div>
          
          <div className="apple-divider-line mb-5" />
          <div className="flex flex-wrap content-center items-center gap-[15px] pl-5 pr-5">
            <div className="log-message w-full whitespace-pre-wrap text-base font-light leading-[1.75] text-white/82">
              <div 
                className="markdown-content prose prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: htmlContent }}
              />
            </div>
          </div>
          
          {/* Display web search sources if available */}
          {hasWebSources && webSources.length > 0 && (
            <div className="mt-4 border-t border-white/8 pt-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="apple-panel flex h-8 w-8 items-center justify-center rounded-xl border-white/10 bg-white/[0.05]">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="2" y1="12" x2="22" y2="12"></line>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                  </svg>
                </div>
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-white/46">新增来源</span>
              </div>
              <Sources sources={webSources} compact={true} />
            </div>
          )}
        </div>
      </div>
    );
} 
