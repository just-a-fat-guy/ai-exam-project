export interface BaseData {
  type: string;
}

export interface BasicData extends BaseData {
  type: 'basic';
  content: string;
}

export interface ReportStreamData extends BaseData {
  type: 'report';
  output: string;
  content?: string;
  metadata?: any;
}

export interface ReportCompleteData extends BaseData {
  type: 'report_complete';
  output: string;
  content?: string;
  metadata?: any;
}

export interface LanggraphButtonData extends BaseData {
  type: 'langgraphButton';
  link: string;
}

export interface DifferencesData extends BaseData {
  type: 'differences';
  content: string;
  output: string;
}

export interface QuestionData extends BaseData {
  type: 'question';
  content: string;
}

export interface ChatData extends BaseData {
  type: 'chat';
  content: string;
  metadata?: any; // For storing search results and other contextual information
}

export interface LogData extends BaseData {
  type: 'logs';
  content: string;
  output: any;
  metadata?: any;
}

export interface PathData extends BaseData {
  type: 'path';
  output: any;
  content?: string;
  metadata?: any;
}

export type Data =
  | BasicData
  | ReportStreamData
  | ReportCompleteData
  | LanggraphButtonData
  | DifferencesData
  | QuestionData
  | ChatData
  | LogData
  | PathData;

export interface MCPConfig {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface ChatBoxSettings {
  workflow_mode?: string;
  report_type: string;
  report_source: string;
  tone: string;
  domains: string[];
  defaultReportType: string;
  layoutType: string;
  mcp_enabled: boolean;
  mcp_configs: MCPConfig[];
  mcp_strategy?: string;
  generation_mode?: string;
  include_answers?: boolean;
  include_explanations?: boolean;
  output_formats?: string[];
}

export interface Domain {
  value: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: number;
  metadata?: any; // For storing search results and other contextual information
}

export interface ConversationThreadItem {
  id: string;
  role: "user" | "assistant" | "system";
  kind: "message" | "exam_preview" | "status";
  content: string;
  timestamp?: number;
  metadata?: any;
}

export interface ResearchHistoryItem {
  id: string;
  question: string;
  answer: string;
  timestamp: number;
  orderedData: Data[];
  chatMessages?: ChatMessage[];
} 
