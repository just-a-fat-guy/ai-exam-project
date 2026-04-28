import React, { FC, useRef, useState } from "react";
import TypeAnimation from "../../TypeAnimation";

type TChatInputProps = {
  promptValue: string;
  setPromptValue: React.Dispatch<React.SetStateAction<string>>;
  handleSubmit: (query: string) => void;
  disabled?: boolean;
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

const ChatInput: FC<TChatInputProps> = ({
  promptValue,
  setPromptValue,
  handleSubmit,
  disabled,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const placeholder = "对这份报告还有什么想继续追问的？";

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

  return (
    <div className="relative">
      <div
        className={`pointer-events-none absolute inset-0 rounded-[24px] transition-opacity duration-300 ${
          isFocused || promptValue ? "opacity-100" : "opacity-70"
        }`}
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.03) 40%, rgba(255,255,255,0.08) 100%)",
        }}
      />

      <form
        className="apple-panel relative z-10 mx-auto flex w-full items-end gap-3 rounded-[24px] border-white/10 bg-[#0c0c0d]/90 px-4 py-4"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          placeholder={placeholder}
          ref={textareaRef}
          className="my-1 w-full resize-none bg-transparent pl-1 text-base font-light leading-[1.5] text-white outline-none placeholder:text-white/28"
          disabled={disabled}
          value={promptValue}
          required
          rows={3}
          onKeyDown={handleKeyDown}
          onChange={handleTextareaChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />

        <button
          disabled={disabled || !promptValue.trim()}
          type="submit"
          className="apple-button-primary relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <TypeAnimation />
            </div>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
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

export default ChatInput;
