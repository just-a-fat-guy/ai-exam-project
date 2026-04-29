import React, { FC, useEffect, useState, useCallback } from "react";
import ExamRequestForm from "./Exam/ExamRequestForm";
import ExamNaturalRequestForm from "./Exam/ExamNaturalRequestForm";
import InputArea from "./ResearchBlocks/elements/InputArea";
import { motion, AnimatePresence } from "framer-motion";
import { ExamRequestDraft } from "@/types/exam";

type Ripple = {
  id: number;
  x: number;
  y: number;
};

type THeroProps = {
  examDraft?: ExamRequestDraft;
  setExamDraft?: React.Dispatch<React.SetStateAction<ExamRequestDraft>>;
  handleValidateExamRequest?: () => void;
  promptValue?: string;
  setPromptValue?: React.Dispatch<React.SetStateAction<string>>;
  handleDisplayResult?: (query: string) => void;
  loading?: boolean;
  naturalExamRequest?: string;
  setNaturalExamRequest?: React.Dispatch<React.SetStateAction<string>>;
  handleNaturalExamRequest?: () => void;
  showAdvancedExamForm?: boolean;
  toggleAdvancedExamForm?: () => void;
};

const Hero: FC<THeroProps> = ({
  examDraft,
  setExamDraft,
  handleValidateExamRequest,
  promptValue,
  setPromptValue,
  handleDisplayResult,
  loading = false,
  naturalExamRequest,
  setNaturalExamRequest,
  handleNaturalExamRequest,
  showAdvancedExamForm = false,
  toggleAdvancedExamForm,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const isExamMode = Boolean(examDraft && setExamDraft && handleValidateExamRequest);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  // 处理点击波纹效果
  const handleClick = useCallback((e: React.MouseEvent<HTMLElement>) => {
    // 只在点击背景区域时触发，避免点击按钮、输入框等交互元素时也产生波纹
    if ((e.target as HTMLElement).closest('button, textarea, input, a')) {
      return;
    }
    
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const newRipple = {
      id: Date.now() + Math.random(),
      x,
      y,
    };
    
    setRipples(prev => [...prev, newRipple]);
    
    // 自动清理波纹
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id));
    }, 2000);
  }, []);

  const handleClickSuggestion = (value: string) => {
    if (isExamMode && setExamDraft) {
      if (setNaturalExamRequest) {
        setNaturalExamRequest(value);
      }
      return;
    }

    if (setPromptValue) {
      setPromptValue(value);
    }
  };

  const fadeInUp = {
    hidden: { opacity: 0, y: 28 },
    visible: { opacity: 1, y: 0 },
  };

  return (
    <section 
      className={`relative overflow-hidden cursor-default ${
        isExamMode ? "h-full min-h-0 py-6" : "min-h-[90vh] pb-20 pt-[80px]"
      }`}
      onClick={handleClick}
    >      <div className="apple-noise pointer-events-none absolute inset-0 opacity-80" />

      {/* 动态背景光晕层 */}
      <motion.div
        animate={{
          scale: [1, 1.05, 1],
          opacity: [0.3, 0.4, 0.3],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute inset-x-0 top-40 mx-auto h-[380px] w-[380px] rounded-full bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-pink-500/20 blur-[120px] sm:h-[480px] sm:w-[480px]"
      />
      <motion.div
        animate={{
          x: [0, 20, 0],
          opacity: [0.2, 0.3, 0.2],
        }}
        transition={{
          duration: 12,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute -left-24 top-1/3 h-[280px] w-[280px] rounded-full bg-cyan-400/20 blur-[90px]"
      />
      <motion.div
        animate={{
          x: [0, -20, 0],
          opacity: [0.2, 0.3, 0.2],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute -right-24 bottom-10 h-[320px] w-[320px] rounded-full bg-indigo-500/20 blur-[110px]"
      />
      
      {/* 新增彩色动态光晕 */}
      <motion.div
        animate={{
          y: [0, 30, 0],
          opacity: [0.15, 0.25, 0.15],
        }}
        transition={{
          duration: 15,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute left-1/4 top-1/2 h-[250px] w-[250px] rounded-full bg-pink-500/20 blur-[100px]"
      />
      <motion.div
        animate={{
          y: [0, -25, 0],
          opacity: [0.1, 0.2, 0.1],
        }}
        transition={{
          duration: 18,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute right-1/4 top-1/4 h-[220px] w-[220px] rounded-full bg-orange-400/15 blur-[90px]"
      />
      <motion.div
        animate={{
          scale: [0.9, 1.1, 0.9],
          opacity: [0.12, 0.2, 0.12],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute left-1/3 bottom-1/4 h-[300px] w-[300px] rounded-full bg-teal-400/15 blur-[100px]"
      />

      <div className="pointer-events-none absolute inset-x-0 top-[18%] mx-auto h-px max-w-[980px] bg-gradient-to-r from-transparent via-white/30 to-transparent apple-chrome-line" />

      {/* 上下渐变光带 */}
      <motion.div
        animate={{
          opacity: [0.1, 0.2, 0.1],
          y: [0, 10, 0],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-purple-500/10 to-transparent"
      />
      <motion.div
        animate={{
          opacity: [0.1, 0.18, 0.1],
          y: [0, -10, 0],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-blue-500/10 to-transparent"
      />

      {/* 点击波纹容器 */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <AnimatePresence>
          {ripples.map(ripple => (
            <motion.div
              key={ripple.id}
              initial={{ scale: 0, opacity: 0.4 }}
              animate={{ scale: 4, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 2, ease: "easeOut" }}
              className="absolute rounded-full bg-gradient-to-r from-purple-500/30 to-blue-500/30 blur-xl"
              style={{
                left: ripple.x - 50,
                top: ripple.y - 50,
                width: 100,
                height: 100,
              }}
            />
          ))}
        </AnimatePresence>
      </div>

      <motion.div
        initial="hidden"
        animate={isVisible ? "visible" : "hidden"}
        variants={fadeInUp}
        transition={{ duration: 0.8 }}
        className={`relative z-10 mx-auto flex w-full max-w-[1240px] flex-col items-center px-4 ${
          isExamMode ? "h-full justify-center" : ""
        }`}
      >
        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.7, delay: 0.05 }}
          className={`apple-chip inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.28em] ${
            isExamMode ? "mb-4" : "mb-6"
          }`}
        >
          <span className="h-2 w-2 rounded-full bg-white/70" />
          {isExamMode ? "AI 组卷引擎" : "AI 研究引擎"}
        </motion.div>

        <motion.h1
          variants={fadeInUp}
          transition={{ duration: 0.85, delay: 0.12 }}
          className={`bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent max-w-[980px] text-center font-semibold leading-[0.95] tracking-[-0.06em] drop-shadow-[0_0_30px_rgba(139,92,246,0.2)] ${
            isExamMode ? "text-4xl sm:text-5xl lg:text-6xl" : "text-5xl sm:text-6xl lg:text-8xl"
          }`}
        >
          {isExamMode ? "AI 智能组卷" : (
            <>
              以更安静的界面，
              <br />
              做更锋利的研究。
            </>
          )}
        </motion.h1>

        <motion.p
          variants={fadeInUp}
          transition={{ duration: 0.7, delay: 0.2 }}
          className={`max-w-[760px] text-center leading-7 text-white/58 ${
            isExamMode ? "mt-3 text-sm sm:text-base" : "mt-4 text-base sm:text-lg"
          }`}
        >
          {isExamMode
            ? "输入一句话需求，AI自动组卷。"
            : "黑白灰的主视觉、更克制的层次和更强的专注感。输入一个问题，GPT Researcher 会把检索、整理、归纳和成压缩到同一条工作流里。"}
        </motion.p>

        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.85, delay: 0.28 }}
          className={`relative w-full max-w-[960px] ${
            isExamMode ? "mt-6 flex-1 min-h-0" : "mt-8"
          }`}
        >
          <div className="pointer-events-none absolute inset-x-[14%] -top-10 h-28 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 blur-[90px]" />
          <motion.div
            whileHover={{ scale: 1.01 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className={`apple-panel-strong rounded-[34px] border border-white/10 bg-gradient-to-br from-black/40 via-black/50 to-black/40 backdrop-blur-xl shadow-[0_0_50px_rgba(139,92,246,0.1)] ${
              isExamMode ? "flex h-full min-h-0 flex-col p-3 sm:p-4" : "p-3 sm:p-4"
            }`}
          >
            {isExamMode && examDraft && setExamDraft && handleValidateExamRequest ? (
              <div className={`space-y-4 ${showAdvancedExamForm ? "min-h-0 overflow-y-auto no-scrollbar pr-1" : ""}`}>
                <ExamNaturalRequestForm
                  value={naturalExamRequest || ""}
                  onChange={setNaturalExamRequest || (() => undefined)}
                  onSubmit={handleNaturalExamRequest || handleValidateExamRequest}
                  disabled={loading}
                  showAdvanced={showAdvancedExamForm}
                  onToggleAdvanced={toggleAdvancedExamForm}
                />
                {showAdvancedExamForm && (
                  <ExamRequestForm
                    draft={examDraft}
                    setDraft={setExamDraft}
                    onSubmit={handleValidateExamRequest}
                    disabled={loading}
                  />
                )}
              </div>
            ) : (
              <InputArea
                promptValue={promptValue || ""}
                setPromptValue={setPromptValue || (() => undefined)}
                handleSubmit={handleDisplayResult || (() => undefined)}
                disabled={loading}
              />
            )}
          </motion.div>
        </motion.div>

        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.8, delay: 0.38 }}
          className={`flex w-full max-w-[1120px] flex-wrap items-center justify-center gap-3 ${
            isExamMode ? "mt-5" : "mt-10"
          }`}
        >
          {suggestions.map((item, index) => (
            <motion.button
              key={item.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.48 + index * 0.08 }}
              onClick={() => handleClickSuggestion(item.name)}
              className={`apple-chip group rounded-[24px] text-left ${
                isExamMode
                  ? "min-w-[220px] flex-1 px-4 py-3 sm:min-w-[240px] sm:flex-none"
                  : "min-w-[220px] px-5 py-4 sm:min-w-[260px]"
              }`}
              whileHover={{ y: -3, scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className={`flex items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ${
                isExamMode ? "mb-3 h-10 w-10" : "mb-4 h-11 w-11"
              }`}>
                <img
                  src={item.icon}
                  alt={item.name}
                  width={18}
                  height={18}
                  className="opacity-80 invert"
                />
              </div>
              <div className={`font-medium text-white/88 ${isExamMode ? "text-[13px] leading-6" : "text-sm"}`}>{item.name}</div>
              <div className="mt-1 text-xs tracking-[0.18em] uppercase text-white/38">
                快速开始
              </div>
            </motion.button>
          ))}
        </motion.div>
      </motion.div>
    </section>
  );
};

type SuggestionType = {
  id: number;
  name: string;
  icon: string;
};

const suggestions: SuggestionType[] = [
  {
    id: 1,
    name: "小学语文三年级下册期末考试试卷，难度一般。",
    icon: "/img/stock2.svg",
  },
  {
    id: 2,
    name: "初中数学八年级上册单元测试卷，难度中等偏上。",
    icon: "/img/news.svg",
  },
  {
    id: 3,
    name: "小学数学六年级下册期末考试试卷，基础题和应用题比例均衡。",
    icon: "/img/hiker.svg",
  },
];

export default Hero;
