import Image from "next/image";
import LogMessage from './elements/LogMessage';
import { useEffect, useRef } from 'react';

interface Log {
  header: string;
  text: string;
  metadata: any;
  key: string;
}

interface OrderedLogsProps {
  logs: Log[];
}

const LogsSection = ({ logs }: OrderedLogsProps) => {
  const logsContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to bottom whenever logs change
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs]); // Dependency on logs array ensures this runs when new logs are added

  return (
    <div className="container apple-panel mt-5 h-auto w-full shrink-0 rounded-[30px] border-white/8 p-6">
      <div className="flex items-start gap-4 pb-4 lg:pb-4">
        <div className="apple-panel flex h-11 w-11 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
          <img src="/img/chat-check.svg" alt="logs" width={20} height={20} className="invert" />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            执行轨迹
          </div>
          <h3 className="text-sm font-medium text-white/84">
            Agent 工作过程
          </h3>
        </div>
      </div>
      <div className="apple-divider-line mb-5" />
      <div 
        ref={logsContainerRef}
        className="overflow-y-auto min-h-[200px] max-h-[500px] scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-300/10"
      >
        <LogMessage logs={logs} />
      </div>
    </div>
  );
};

export default LogsSection; 
