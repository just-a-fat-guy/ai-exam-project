import React, { ChangeEvent } from 'react';

interface ToneSelectorProps {
  tone: string;
  onToneChange: (event: ChangeEvent<HTMLSelectElement>) => void;
}
export default function ToneSelector({ tone, onToneChange }: ToneSelectorProps) {
  return (
    <div className="form-group">
      <label htmlFor="tone" className="agent_question">语气风格 </label>
      <select 
        name="tone" 
        id="tone" 
        value={tone} 
        onChange={onToneChange} 
        className="form-control-static"
        required
      >
        <option value="Objective">客观 - 中立、克制地呈现事实与结论</option>
        <option value="Formal">正式 - 更符合学术或专业写作风格</option>
        <option value="Analytical">分析型 - 强调拆解、比较与推理</option>
        <option value="Persuasive">说服型 - 更强调论证与观点成立</option>
        <option value="Informative">信息型 - 清晰完整地传递信息</option>
        <option value="Explanatory">解释型 - 更注重说明复杂概念和过程</option>
        <option value="Descriptive">描述型 - 更强调细节、现象与案例描写</option>
        <option value="Critical">批判型 - 强调局限、有效性与相关性判断</option>
        <option value="Comparative">比较型 - 突出不同方法、数据或观点的异同</option>
        <option value="Speculative">推测型 - 讨论假设、影响与未来方向</option>
        <option value="Reflective">反思型 - 更强调过程反思与个人洞察</option>
        <option value="Narrative">叙述型 - 用故事化方式组织内容</option>
        <option value="Humorous">轻松幽默 - 更易读、更有亲和力</option>
        <option value="Optimistic">乐观 - 更突出积极结果与潜在收益</option>
        <option value="Pessimistic">谨慎悲观 - 更强调风险、限制与挑战</option>
        <option value="Simple">简明 - 面向初学者，词汇更基础</option>
        <option value="Casual">口语化 - 更接近日常交流表达</option>
      </select>
    </div>
  );
}
