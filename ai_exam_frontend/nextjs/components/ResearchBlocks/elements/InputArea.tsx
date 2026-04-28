import React, { FC, useEffect, useRef, useState } from "react";
import TypeAnimation from "../../TypeAnimation";

type TInputAreaProps = {
  promptValue: string;
  setPromptValue: React.Dispatch<React.SetStateAction<string>>;
  handleSubmit: (query: string) => void;
  handleSecondary?: (query: string) => void;
  disabled?: boolean;
  reset?: () => void;
  isStopped?: boolean;
};

function debounce(func: Function, wait: number) {
  let timeout: NodeJS.Timeout | undefined;
  return function executedFunction(...args: any[]) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

const InputArea: FC<TInputAreaProps> = ({
  promptValue,
  setPromptValue,
  handleSubmit,
  disabled,
  reset,
  isStopped,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const placeholder = "输入你的研究主题、问题，或想深入了解的方向...";

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const resetHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "3em";
    }
  };

  const adjustHeight = debounce((target: HTMLTextAreaElement) => {
    target.style.height = "auto";
    target.style.height = `${target.scrollHeight}px`;
  }, 100);

  const submit = () => {
    if (disabled || !promptValue.trim()) return;
    if (reset) reset();
    handleSubmit(promptValue);
    setPromptValue("");
    resetHeight();
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const target = e.target;
    adjustHeight(target);
    setPromptValue(target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  if (isStopped) {
    return null;
  }

  return (
    <div className="relative">
      <div
        className={`pointer-events-none absolute inset-0 rounded-[30px] transition-opacity duration-300 ${
          isFocused || promptValue
            ? "opacity-100"
            : "opacity-70"
        }`}
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 28%, rgba(255,255,255,0.08) 100%)",
        }}
      />
      <div className="pointer-events-none absolute inset-x-[12%] -top-6 h-20 rounded-full bg-white/10 blur-[48px]" />

      <form
        className="apple-panel-strong relative z-10 mx-auto flex w-full items-end gap-4 rounded-[30px] border-white/12 bg-[#0d0d0f]/90 p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="flex-1">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-[0.28em] text-white/36">
              研究输入
            </span>
            <span className="hidden text-xs text-white/26 sm:block">
              Enter 发送，Shift + Enter 换行
            </span>
          </div>

          <textarea
            placeholder={placeholder}
            ref={textareaRef}
            className="my-1 w-full resize-none bg-transparent text-xl font-light leading-[1.5] text-white outline-none placeholder:text-white/30 sm:text-[26px]"
            disabled={disabled}
            value={promptValue}
            required
            rows={3}
            onKeyDown={handleKeyDown}
            onChange={handleTextareaChange}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
          />
        </div>

        <button
          disabled={disabled || !promptValue.trim()}
          type="submit"
          className="apple-button-primary relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <TypeAnimation />
            </div>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          )}
        </button>
      </form>
    </div>
  );
};

export default InputArea;
