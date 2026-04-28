import React, { FC, useEffect, useState } from "react";
import ExamRequestForm from "./Exam/ExamRequestForm";
import InputArea from "./ResearchBlocks/elements/InputArea";
import { motion } from "framer-motion";
import { ExamRequestDraft } from "@/types/exam";

type THeroProps = {
  examDraft?: ExamRequestDraft;
  setExamDraft?: React.Dispatch<React.SetStateAction<ExamRequestDraft>>;
  handleValidateExamRequest?: () => void;
  promptValue?: string;
  setPromptValue?: React.Dispatch<React.SetStateAction<string>>;
  handleDisplayResult?: (query: string) => void;
  loading?: boolean;
};

const Hero: FC<THeroProps> = ({
  examDraft,
  setExamDraft,
  handleValidateExamRequest,
  promptValue,
  setPromptValue,
  handleDisplayResult,
  loading = false,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const isExamMode = Boolean(examDraft && setExamDraft && handleValidateExamRequest);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  const handleClickSuggestion = (value: string) => {
    if (isExamMode && setExamDraft) {
      setExamDraft((prev) => ({
        ...prev,
        notes_to_generator: value,
      }));
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
    <section className="relative min-h-[100vh] overflow-hidden pt-[120px] pb-20">
      <div className="apple-noise pointer-events-none absolute inset-0 opacity-80" />

      <div className="pointer-events-none absolute inset-x-0 top-20 mx-auto h-[420px] w-[420px] rounded-full bg-white/8 blur-[120px] apple-ambient sm:h-[520px] sm:w-[520px]" />
      <div className="pointer-events-none absolute -left-24 top-1/3 h-[280px] w-[280px] rounded-full bg-white/6 blur-[90px] apple-ambient" />
      <div className="pointer-events-none absolute -right-24 bottom-10 h-[320px] w-[320px] rounded-full bg-zinc-300/10 blur-[110px] apple-ambient" />

      <div className="pointer-events-none absolute inset-x-0 top-[18%] mx-auto h-px max-w-[980px] bg-gradient-to-r from-transparent via-white/30 to-transparent apple-chrome-line" />

      <motion.div
        initial="hidden"
        animate={isVisible ? "visible" : "hidden"}
        variants={fadeInUp}
        transition={{ duration: 0.8 }}
        className="relative z-10 mx-auto flex w-full max-w-[1240px] flex-col items-center px-4"
      >
        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.7, delay: 0.05 }}
          className="apple-chip mb-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.28em]"
        >
          <span className="h-2 w-2 rounded-full bg-white/70" />
          {isExamMode ? "AI 组卷引擎" : "AI 研究引擎"}
        </motion.div>

        <motion.h1
          variants={fadeInUp}
          transition={{ duration: 0.85, delay: 0.12 }}
          className="apple-heading-gradient max-w-[980px] text-center text-5xl font-semibold leading-[0.95] tracking-[-0.06em] sm:text-6xl lg:text-8xl"
        >
          {isExamMode ? (
            <>
              先把试卷约束结构化，
              <br />
              再让后端判断它是否可执行。
            </>
          ) : (
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
          className="mt-6 max-w-[760px] text-center text-base leading-7 text-white/58 sm:text-lg"
        >
          {isExamMode
            ? "这一阶段先打通 AI 组卷请求的前端表单和后端验证接口。目标不是立即出卷，而是先把学科、题型、分值、知识点和组卷模式这类输入固定下来。"
            : "黑白灰的主视觉、更克制的层次和更强的专注感。输入一个问题，GPT Researcher 会把检索、整理、归纳和成文压缩到同一条工作流里。"}
        </motion.p>

        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.85, delay: 0.28 }}
          className="relative mt-12 w-full max-w-[960px]"
        >
          <div className="pointer-events-none absolute inset-x-[14%] -top-10 h-28 rounded-full bg-white/12 blur-[90px]" />
          <div className="apple-panel-strong rounded-[34px] p-3 sm:p-4">
            {isExamMode && examDraft && setExamDraft && handleValidateExamRequest ? (
              <ExamRequestForm
                draft={examDraft}
                setDraft={setExamDraft}
                onSubmit={handleValidateExamRequest}
                disabled={loading}
              />
            ) : (
              <InputArea
                promptValue={promptValue || ""}
                setPromptValue={setPromptValue || (() => undefined)}
                handleSubmit={handleDisplayResult || (() => undefined)}
                disabled={loading}
              />
            )}
          </div>
          <p className="mt-5 text-center text-sm text-white/42">
            {isExamMode
              ? "当前只校验请求结构和业务一致性，不会直接生成试卷正文。"
              : "GPT Researcher 可能会出错。重要结论请自行复核，并检查来源引用。"}
          </p>
        </motion.div>

        <motion.div
          variants={fadeInUp}
          transition={{ duration: 0.8, delay: 0.38 }}
          className="mt-12 flex w-full max-w-[1120px] flex-wrap items-center justify-center gap-3"
        >
          {suggestions.map((item, index) => (
            <motion.button
              key={item.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.48 + index * 0.08 }}
              onClick={() => handleClickSuggestion(item.name)}
              className="apple-chip group min-w-[220px] rounded-[24px] px-5 py-4 text-left sm:min-w-[260px]"
              whileHover={{ y: -3, scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
                <img
                  src={item.icon}
                  alt={item.name}
                  width={18}
                  height={18}
                  className="opacity-80 invert"
                />
              </div>
              <div className="text-sm font-medium text-white/88">{item.name}</div>
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
    name: "整体难度前易后难，压轴题控制在最后一题",
    icon: "/img/stock2.svg",
  },
  {
    id: 2,
    name: "优先从题库抽题，不足部分再允许 AI 补题",
    icon: "/img/news.svg",
  },
  {
    id: 3,
    name: "知识点覆盖要均衡，避免偏题和超纲内容",
    icon: "/img/hiker.svg",
  },
];

export default Hero;
