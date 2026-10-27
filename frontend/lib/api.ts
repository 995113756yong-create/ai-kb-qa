import { createSSEParser } from "@/lib/sse";
import type {
  AgentEvent,
  AskResponse,
  DeleteResponse,
  DocListResponse,
  UploadResponse,
} from "@/lib/types";

// 所有请求都打到同源的 /api/*，由 Route Handler 转发给 FastAPI。

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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

export function listDocs(): Promise<DocListResponse> {
  return requestJson<DocListResponse>("/api/docs");
}

export function uploadDoc(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<UploadResponse>("/api/upload", { method: "POST", body: form });
}

export function deleteDoc(docId: string): Promise<DeleteResponse> {
  return requestJson<DeleteResponse>(`/api/docs/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
}

export function ask(question: string): Promise<AskResponse> {
  return requestJson<AskResponse>("/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export async function streamAgent(
  question: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/agent/stream", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
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
  const parser = createSSEParser(onEvent);

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.flush();
}
