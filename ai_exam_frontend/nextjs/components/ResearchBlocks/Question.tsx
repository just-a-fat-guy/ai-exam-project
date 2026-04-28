import React from 'react';
import Image from "next/image";

interface QuestionProps {
  question: string;
}

const Question: React.FC<QuestionProps> = ({ question }) => {
  return (
    <div className="container apple-panel mt-5 mb-5 flex w-full flex-col items-start gap-4 rounded-[28px] px-5 py-5 sm:flex-row sm:px-6">
      <div className="flex items-center gap-3 sm:gap-4">
        <div className="apple-panel flex h-12 w-12 items-center justify-center rounded-2xl border-white/10 bg-white/[0.05]">
          <img
            src={"/img/message-question-circle.svg"}
            alt="message"
            width={22}
            height={22}
            className="w-5 h-5 invert"
          />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            当前任务
          </div>
          <div className="text-sm font-medium text-white/78">任务摘要</div>
        </div>
      </div>
      <div className="log-message mt-1 max-w-full grow break-words text-lg font-medium text-white/88 sm:mt-0">
        {question}
      </div>
    </div>
  );
};

export default Question;
