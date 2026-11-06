import { createSSEParser } from "@/lib/sse";
import type {
  AgentCreateRequest,
  AgentEvent,
  AgentListResponse,
  ChunkResponse,
  FeedbackRequest,
  AskResponse,
  DeleteResponse,
  HistoryTurn,
  DocListResponse,
  UploadResponse,
} from "@/lib/types";

// 所有请求都打到同源的 /api/*，由 Route Handler 转发给 FastAPI。
// agent_id 通过查询串传给后端（POST body 也可以，但查询串对转发层完全透明，
// 不用改 route.ts 的任何逻辑）。default 专家沿用无参数的旧路径。

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** 从 fetch Response 构造：读取 body 里的 detail 转成可读文案。 */
  static async from(res: Response): Promise<ApiError> {
    return new ApiError(res.status, toMessage(res.status, await readBody(res)));
  }
}

type DetailItem = { msg?: string };
type ErrorBody = { detail?: string | DetailItem[] };

function toMessage(status: number, body: unknown): string {
  const detail = (body as ErrorBody | null)?.detail;
  if (typeof detail === "string" && detail) {
    return detail;
  }
  // FastAPI 的 422 校验错误是数组，把各项的 msg 拼起来
  if (Array.isArray(detail)) {
    const joined = detail
      .map((item) => (typeof item?.msg === "string" ? item.msg : ""))
      .filter(Boolean)
      .join("; ");
    if (joined) {
      return joined;
    }
  }
  return `HTTP ${status}`;
}

async function readBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  if (!res.ok) {
    throw new ApiError(res.status, toMessage(res.status, await readBody(res)));
  }
  return (await res.json()) as T;
}

const DEFAULT_AGENT = "default";
const ADMIN_TOKEN_KEY = "kbqa_admin_token";

/** 管理员口令：用户输入一次后存 localStorage，写接口都带上。 */
export function adminHeaders(): Record<string, string> {
  if (typeof window === "undefined") {
    return {};
  }
  const token = window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
  return token ? { "X-Admin-Token": token } : {};
}

function saveAdminToken(token: string): void {
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

/** 401 时提示输入口令，保存后重试一次；取消或仍失败则抛最后收到的错误。 */
async function withAdminRetry<T>(
  run: (headers: Record<string, string>) => Promise<T>,
): Promise<T> {
  try {
    return await run(adminHeaders());
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 401) {
      throw err;
    }
    const token =
      typeof window !== "undefined" ? window.prompt("请输入管理员口令") ?? "" : "";
    if (!token) {
      throw err;
    }
    saveAdminToken(token);
    return run(adminHeaders());
  }
}

/** 专家级路径：default 不带参数（保持旧路径），其余专家带 ?agent_id=。 */
function agentQuery(agentId: string | undefined): string {
  if (!agentId || agentId === DEFAULT_AGENT) {
    return "";
  }
  return `?agent_id=${encodeURIComponent(agentId)}`;
}

export function listDocs(agentId?: string): Promise<DocListResponse> {
  return requestJson<DocListResponse>(`/api/docs${agentQuery(agentId)}`);
}

export function uploadDoc(file: File, agentId?: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return withAdminRetry((headers) =>
    requestJson<UploadResponse>(`/api/upload${agentQuery(agentId)}`, {
      method: "POST",
      body: form,
      headers,
    }),
  );
}

export function deleteDoc(docId: string, agentId?: string): Promise<DeleteResponse> {
  return withAdminRetry((headers) =>
    requestJson<DeleteResponse>(
      `/api/docs/${encodeURIComponent(docId)}${agentQuery(agentId)}`,
      { method: "DELETE", headers },
    ),
  );
}

export function ask(question: string, agentId?: string): Promise<AskResponse> {
  return requestJson<AskResponse>(`/api/ask${agentQuery(agentId)}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

// ---------- 多专家平台 ----------

export function listAgents(): Promise<AgentListResponse> {
  return requestJson<AgentListResponse>("/api/agents");
}

export function createAgent(
  req: AgentCreateRequest,
): Promise<{ status: "ok" } & Record<string, unknown>> {
  return withAdminRetry((headers) =>
    requestJson("/api/agents", {
      method: "POST",
      headers: { "content-type": "application/json", ...headers },
      body: JSON.stringify(req),
    }),
  );
}

export function deleteAgent(agentId: string): Promise<DeleteResponse> {
  return withAdminRetry((headers) =>
    requestJson<DeleteResponse>(`/api/agents/${encodeURIComponent(agentId)}`, {
      method: "DELETE",
      headers,
    }),
  );
}

// ---------- Agent SSE ----------

export type StreamAgentOptions = {
  question: string;
  onEvent: (event: AgentEvent) => void;
  signal?: AbortSignal;
  /** strict = 拒答优先；reference = 默认引用模式。 */
  mode?: "strict" | "reference";
  agentId?: string;
  /** 多轮：最近几轮对话，只用于把追问改写成独立问题 */
  history?: HistoryTurn[];
};

export async function streamAgent(
  questionOrOptions: string | StreamAgentOptions,
  onEvent?: (event: AgentEvent) => void,
  signal?: AbortSignal,
  agentId?: string,
): Promise<void> {
  // 兼容两种调用：位置参数（旧）与对象参数（新，可带 mode）。
  const opts: StreamAgentOptions =
    typeof questionOrOptions === "string"
      ? { question: questionOrOptions, onEvent: onEvent ?? (() => {}), signal, agentId }
      : questionOrOptions;
  const { question, signal: sig } = opts;
  const cb = opts.onEvent;
  const aid = opts.agentId;
  // agent_id 必须放进请求体：后端 AgentRequest 只解析 body，
  // 只放 URL 查询串会被忽略（曾在多专家平台上线时踩过这个坑）。
  const body: Record<string, unknown> = { question };
  if (opts.history && opts.history.length) body.history = opts.history;
  if (aid && aid !== DEFAULT_AGENT) {
    body.agent_id = aid;
  }
  if (opts.mode === "strict") {
    body.answer_mode = "strict";
  }
  const res = await fetch(`/api/agent/stream${agentQuery(aid)}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: sig,
    cache: "no-store",
  });

  if (!res.ok) {
    throw new ApiError(res.status, toMessage(res.status, await readBody(res)));
  }
  if (!res.body) {
    throw new ApiError(res.status, "响应没有可读取的流");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser(cb);

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.flush();
}

export async function getChunk(
  chunkId: string,
  agentId: string,
  neighbors = 1,
): Promise<ChunkResponse> {
  // 后端读的是 neighbors；旧代码传 window 被忽略，导致"展开上下文"点了没反应
  const params = new URLSearchParams({ agent_id: agentId, neighbors: String(neighbors) });
  const res = await fetch(`/api/chunks/${encodeURIComponent(chunkId)}?${params}`);
  if (!res.ok) {
    throw await ApiError.from(res);
  }
  return (await res.json()) as ChunkResponse;
}

export async function sendFeedback(req: FeedbackRequest): Promise<void> {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw await ApiError.from(res);
  }
}
