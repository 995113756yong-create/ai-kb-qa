// 与后端一一对应的类型定义，接口结构见 README 的「接口」一节。

export type DocInfo = {
  doc_id: string;
  filename: string;
  ext: string;
  size: number;
  chunks: number;
  uploaded_at: string;
};

export type DocListResponse = {
  status: "ok";
  docs: DocInfo[];
};

export type UploadResponse = {
  status: "ok";
  doc_id: string;
  filename: string;
  size: number;
  chunks: number;
  message: string;
};

export type DeleteResponse = {
  status: "ok";
  doc_id: string;
  filename: string;
};

export type Source = {
  index: number;
  doc_id: string | null;
  source: string | null;
  page: number | null;
  snippet: string;
  /** 片段全文：数字一致性检查与 judge 都需要 */
  content?: string;
};

/** 句子级溯源：一段原文 + 程序标注的来源类型 */
export type Segment = {
  text: string;
  kind: "kb" | "general" | "neutral";
  citations: number[];
  warnings: string[];
};

export type UsageInfo = {
  prompt_tokens: number;
  completion_tokens: number;
  llm_calls: number;
};

export type AskResponse = {
  status: "ok";
  question: string;
  answer: string;
  sources: Source[];
};

// ---------- 多专家平台 ----------

export type AgentInfo = {
  agent_id: string;
  name: string;
  description: string;
  persona: string;
  greeting: string;
  emoji: string;
  model: string;
  answer_mode?: "strict" | "reference";
  created_at: string;
  builtin: boolean;
};

export type AgentListResponse = {
  status: "ok";
  agents: AgentInfo[];
};

export type AgentCreateRequest = {
  name: string;
  description?: string;
  persona?: string;
  greeting?: string;
  emoji?: string;
  model?: string;
  answer_mode?: "strict" | "reference";
  agent_id?: string;
};

export type ToolCallArgs = Record<string, unknown>;

type StepEvent = { type: "step"; step: number };
type DecomposeEvent = { type: "decompose"; step: number; queries: string[] };
type ThoughtEvent = { type: "thought"; step: number; text: string };
type ToolCallEvent = {
  type: "tool_call";
  step: number;
  id: string;
  name: string;
  args: ToolCallArgs;
};
type ToolResultEvent = {
  type: "tool_result";
  step: number;
  id: string;
  name: string;
  ok: boolean;
  summary: string;
};
type AnswerDeltaEvent = { type: "answer_delta"; text: string };
type FinalEvent = {
  type: "final";
  answer: string;
  sources: Source[];
  grounded: boolean;
  steps: number;
  elapsed_ms: number;
  agent_id?: string;
  mode?: "strict" | "reference";
  grounded_ratio?: number | null;
  segments?: Segment[];
  usage?: UsageInfo;
};
type ErrorEvent = { type: "error"; detail: string };

// 按 type 区分的联合类型，消费端用 switch (event.type) 即可收窄
export type AgentEvent =
  | StepEvent
  | DecomposeEvent
  | ThoughtEvent
  | ToolCallEvent
  | ToolResultEvent
  | AnswerDeltaEvent
  | FinalEvent
  | ErrorEvent;

export type AgentEventType = AgentEvent["type"];

export type ChatMode = "agent" | "fast";
