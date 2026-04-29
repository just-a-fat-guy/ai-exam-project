"use client";

interface ExamNaturalRequestFormProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  showAdvanced?: boolean;
  onToggleAdvanced?: () => void;
}

export default function ExamNaturalRequestForm({
  value,
  onChange,
  onSubmit,
  disabled = false,
  showAdvanced = false,
  onToggleAdvanced,
}: ExamNaturalRequestFormProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-[26px] border border-white/8 bg-white/[0.02] p-5">
        <div className="mb-3 text-[11px] uppercase tracking-[0.22em] text-white/34">
          自然语言组卷需求
        </div>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="例如：小学语文三年级下册期末考试试卷，难度一般。"
          rows={5}
          disabled={disabled}
          className="w-full rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-4 text-sm leading-7 text-white outline-none placeholder:text-white/24 transition-all duration-300 hover:border-purple-500/30 hover:bg-white/[0.05] focus:border-purple-500/50 focus:bg-white/[0.06] focus:shadow-[0_0_0_3px_rgba(139,92,246,0.1),0_0_20px_rgba(139,92,246,0.15)]"
        />
        <div className="mt-3 text-xs leading-6 text-white/46">
          先输入一句话需求，系统会自动解析学科、年级、考试类型、难度，并按默认模板补全组卷结构。
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          className="apple-button-primary rounded-full px-5 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabled ? "处理中..." : "开始智能组卷"}
        </button>
        {onToggleAdvanced && (
          <button
            type="button"
            onClick={onToggleAdvanced}
            disabled={disabled}
            className="apple-button-ghost rounded-full px-4 py-3 text-sm text-white/62"
          >
            {showAdvanced ? "收起高级参数" : "展开高级参数"}
          </button>
        )}
      </div>
    </div>
  );
}
