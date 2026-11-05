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
  /** 后端 evidence.finalize 附带的片段定位（B6 展开上下文用） */
  chunk_id?: string;
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

/** B7：tool_result 事件携带的命中片段（emit_phases 开启时） */
export type SearchHit = {
  chunk_id: string;
  doc_id: string | null;
  filename: string | null;
  text: string;
  score?: number;
};

/** B6：GET /api/chunks/{chunk_id} 响应 */
export type ChunkResponse = {
  status: "ok";
  chunk_id: string;
  text: string;
  neighbors?: { before: string[]; after: string[] };
};

/** POST /api/feedback 请求体 */
export type FeedbackRequest = {
  agent_id?: string;
  question: string;
  answer: string;
  rating: "up" | "down";
  reason?: string;
  mode?: string | null;
  grounded_ratio?: number | null;
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
  /** B3：推荐问题，旧条目由后端补 [] */
  starter_questions?: string[];
  /** B2：文档数（list 接口返回；get 单个不一定带） */
  doc_count?: number;
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
  starter_questions?: string[];
};

export type ToolCallArgs = Record<string, unknown>;

type StepEvent = { type: "step"; step: number };
type IntentEvent = { type: "intent"; intent: "chat" | "list_docs" | "kb_query" | "uncertain"; reason: string };
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
  /** B7：emit_phases 开启时携带命中片段，证据面板用 */
  hits?: SearchHit[];
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
type PhaseEvent = { type: "phase"; phase: "research" | "answer" };

// 按 type 区分的联合类型，消费端用 switch (event.type) 即可收窄
export type AgentEvent =
  | StepEvent
  | IntentEvent
  | DecomposeEvent
  | ThoughtEvent
  | ToolCallEvent
  | ToolResultEvent
  | AnswerDeltaEvent
  | FinalEvent
  | ErrorEvent
  | PhaseEvent;

export type AgentEventType = AgentEvent["type"];

export type ChatMode = "agent" | "fast";

// eval --json 导出的单次运行摘要（评测看板页数据源）
export type EvalRunSummary = {
  commit: string;
  generated_at: string;
  dataset: string;
  metrics: {
    latency_p50_ms?: number;
    latency_p95_ms?: number;
    grounded_ratio_avg?: number;
    judge_pass_rate?: number;
  };
  modes: {
    strict: ModeSummary;
    reference: ModeSummary;
  };
  failures: { question: string; reason: string }[];
};

export type ModeSummary = {
  total: number;
  passed: number;
  grounded_avg: number | null;
  latency_avg_ms: number | null;
  judge_passed?: number | null;
};
