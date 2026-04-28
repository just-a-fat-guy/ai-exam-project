// /multi_agents/frontend/components/HumanFeedback.tsx

import React, { useState, useEffect } from 'react';

interface HumanFeedbackProps {
  websocket: WebSocket | null;
  onFeedbackSubmit: (feedback: string | null) => void;
  questionForHuman: boolean;
}

const HumanFeedback: React.FC<HumanFeedbackProps> = ({ questionForHuman, websocket, onFeedbackSubmit }) => {
  const [feedbackRequest, setFeedbackRequest] = useState<string | null>(null);
  const [userFeedback, setUserFeedback] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onFeedbackSubmit(userFeedback === '' ? null : userFeedback);
    setFeedbackRequest(null);
    setUserFeedback('');
  };

  return (
    <div className="apple-panel mx-auto max-w-2xl rounded-[28px] p-5 text-white">
      <h3 className="mb-2 text-lg font-semibold text-white/88">需要人工反馈</h3>
      <p className="mb-4 text-white/62">{questionForHuman}</p>
      <form onSubmit={handleSubmit}>
        <textarea
          className="w-full rounded-[20px] border border-white/10 bg-white/[0.04] p-4 text-white outline-none placeholder:text-white/28"
          value={userFeedback}
          onChange={(e) => setUserFeedback(e.target.value)}
          placeholder="在这里输入你的反馈；如果没有补充，也可以直接提交。"
        />
        <button
          type="submit"
          className="apple-button-primary mt-3 rounded-full px-5 py-2 text-sm font-medium"
        >
          提交反馈
        </button>
      </form>
    </div>
  );
};

export default HumanFeedback;
