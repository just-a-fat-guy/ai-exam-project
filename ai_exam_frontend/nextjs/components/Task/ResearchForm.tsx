import React from "react";
import LayoutSelector from "../Settings/LayoutSelector";
import { ChatBoxSettings } from "@/types/data";

interface ResearchFormProps {
  chatBoxSettings: ChatBoxSettings;
  setChatBoxSettings: React.Dispatch<React.SetStateAction<ChatBoxSettings>>;
}

const outputFormatOptions = [
  { value: "json", label: "JSON" },
  { value: "docx", label: "DOCX" },
  { value: "pdf", label: "PDF" },
];

export default function ResearchForm({
  chatBoxSettings,
  setChatBoxSettings,
}: ResearchFormProps) {
  const {
    generation_mode = "ai_generate_only",
    include_answers = true,
    include_explanations = true,
    output_formats = ["json", "docx"],
    layoutType = "research",
  } = chatBoxSettings;

  const onFieldChange = (name: keyof ChatBoxSettings, value: any) => {
    setChatBoxSettings((prevSettings) => ({
      ...prevSettings,
      [name]: value,
    }));
  };

  const onLayoutChange = (e: { target: { value: any } }) => {
    onFieldChange("layoutType", e.target.value);
  };

  const toggleOutputFormat = (format: string) => {
    const currentFormats = new Set(output_formats);
    if (currentFormats.has(format)) {
      currentFormats.delete(format);
    } else {
      currentFormats.add(format);
    }

    const normalizedFormats = Array.from(currentFormats);
    onFieldChange("output_formats", normalizedFormats.length > 0 ? normalizedFormats : ["json"]);
  };

  return (
    <div className="space-y-5">
      <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-4">
        <div className="mb-4">
          <div className="text-[11px] uppercase tracking-[0.24em] text-white/34">
            Workflow
          </div>
          <div className="mt-1 text-sm font-medium text-white/84">AI 组卷偏好</div>
        </div>

        <div className="space-y-4">
          <label className="block">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-white/36">组卷模式</div>
            <select
              value={generation_mode}
              onChange={(event) => onFieldChange("generation_mode", event.target.value)}
              className="w-full rounded-[16px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none"
            >
              <option value="hybrid" className="bg-[#111214] text-white">
                混合组卷
              </option>
              <option value="question_bank_only" className="bg-[#111214] text-white">
                仅题库抽题
              </option>
              <option value="ai_generate_only" className="bg-[#111214] text-white">
                仅 AI 出题
              </option>
            </select>
          </label>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex items-start gap-3 rounded-[18px] border border-white/8 px-4 py-3 text-sm text-white/74">
              <input
                type="checkbox"
                checked={include_answers}
                onChange={(event) => onFieldChange("include_answers", event.target.checked)}
                className="mt-1 h-4 w-4 rounded border-white/20 bg-transparent"
              />
              <div>
                <div className="font-medium text-white/86">要求答案</div>
                <div className="mt-1 text-xs text-white/44">后续正式组卷时要求返回标准答案。</div>
              </div>
            </label>

            <label className="flex items-start gap-3 rounded-[18px] border border-white/8 px-4 py-3 text-sm text-white/74">
              <input
                type="checkbox"
                checked={include_explanations}
                onChange={(event) => onFieldChange("include_explanations", event.target.checked)}
                className="mt-1 h-4 w-4 rounded border-white/20 bg-transparent"
              />
              <div>
                <div className="font-medium text-white/86">要求解析</div>
                <div className="mt-1 text-xs text-white/44">后续正式组卷时要求同时给出题目解析。</div>
              </div>
            </label>
          </div>

          <div>
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-white/36">输出格式</div>
            <div className="flex flex-wrap gap-3">
              {outputFormatOptions.map((option) => (
                <label
                  key={option.value}
                  className="flex items-center gap-2 rounded-full border border-white/8 px-4 py-2 text-sm text-white/74"
                >
                  <input
                    type="checkbox"
                    checked={output_formats.includes(option.value)}
                    onChange={() => toggleOutputFormat(option.value)}
                    className="h-4 w-4 rounded border-white/20 bg-transparent"
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      <LayoutSelector layoutType={layoutType} onLayoutChange={onLayoutChange} />
    </div>
  );
}
