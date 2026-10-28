"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ChatInput from "@/components/ChatInput";
import DocSidebar from "@/components/DocSidebar";
import MessageList from "@/components/MessageList";
import { ApiError, ask, listDocs, streamAgent } from "@/lib/api";
import type { ChatMessage, Step } from "@/lib/chat";
import type { AgentEvent, ChatMode, DocInfo } from "@/lib/types";

let messageSeq = 0;
function nextId(prefix: string): string {
  messageSeq += 1;
  return `${prefix}-${messageSeq}`;
}

export default function ChatApp() {
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<ChatMode>("agent");
  const [running, setRunning] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 首屏拉列表：setState 只在 fetch 完成后发生，不放在 effect 的同步体里
  const refreshDocs = useCallback(async () => {
    try {
      const data = await listDocs();
      setDocs(data.docs);
    } catch {
      // 列表读不到时保持空态，用户重新上传即可
      setDocs([]);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;

    void listDocs()
      .then((data) => {
        if (alive) {
          setDocs(data.docs);
        }
      })
      .catch(() => {
        if (alive) {
          setDocs([]);
        }
      })
      .finally(() => {
        if (alive) {
          setDocsLoading(false);
        }
      });

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const patchMessage = useCallback((id: string, patch: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? patch(m) : m)));
  }, []);

  const handleAgentEvent = useCallback(
    (id: string, event: AgentEvent) => {
      patchMessage(id, (message) => {
        if (message.role !== "assistant") {
          return message;
        }
        switch (event.type) {
          case "step":
            return message;
          case "thought":
            return {
              ...message,
              steps: [
                ...message.steps,
                { kind: "thought", key: `${id}-t-${message.steps.length}`, text: event.text },
              ],
            };
          case "tool_call":
            return {
              ...message,
              steps: [
                ...message.steps,
                {
                  kind: "tool_call",
                  key: `${id}-c-${event.id}`,
                  name: event.name,
                  args: event.args,
                },
              ],
            };
          case "tool_result":
            return {
              ...message,
              steps: [
                ...message.steps,
                {
                  kind: "tool_result",
                  key: `${id}-r-${event.id}`,
                  name: event.name,
                  ok: event.ok,
                  summary: event.summary,
                },
              ],
            };
          case "answer_delta":
            // 流式阶段先拼原始文本（带 [E1]），final 到达后整体替换成已重编的版本
            return { ...message, answer: message.answer + event.text };
          case "final":
            return {
              ...message,
              answer: event.answer,
              sources: event.sources,
              grounded: event.grounded,
              elapsedMs: event.elapsed_ms,
              running: false,
            };
          case "error":
            return { ...message, error: event.detail, running: false };
          default:
            return message;
        }
      });
    },
    [patchMessage],
  );

  const send = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = { id: nextId("u"), role: "user", text };
      const assistantId = nextId("a");
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        mode,
        steps: [] as Step[],
        answer: "",
        sources: [],
        grounded: true,
        running: true,
        error: null,
        elapsedMs: null,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setRunning(true);
      setDrawerOpen(false);

      if (mode === "fast") {
        try {
          const result = await ask(text);
          patchMessage(assistantId, (m) =>
            m.role === "assistant"
              ? { ...m, answer: result.answer, sources: result.sources, running: false }
              : m,
          );
        } catch (e) {
          const detail = e instanceof ApiError ? e.message : "请求失败，请重试";
          patchMessage(assistantId, (m) =>
            m.role === "assistant" ? { ...m, error: detail, running: false } : m,
          );
        } finally {
          setRunning(false);
        }
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamAgent(text, (event) => handleAgentEvent(assistantId, event), controller.signal);
      } catch (e) {
        // 用户点“停止”会中断 fetch，这里不当作错误
        if (!controller.signal.aborted) {
          const detail = e instanceof ApiError ? e.message : "连接中断，请重试";
          patchMessage(assistantId, (m) =>
            m.role === "assistant" ? { ...m, error: detail, running: false } : m,
          );
        }
      } finally {
        patchMessage(assistantId, (m) =>
          m.role === "assistant" ? { ...m, running: false } : m,
        );
        abortRef.current = null;
        setRunning(false);
      }
    },
    [handleAgentEvent, mode, patchMessage],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }, []);

  const jumpToSource = useCallback((messageId: string, index: number) => {
    const el = document.querySelector(`#${messageId} [data-testid="source-card-${index}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const noDocs = docs.length === 0;

  return (
    <div className="flex h-full min-h-screen flex-col bg-white dark:bg-zinc-950">
      <header className="flex items-center gap-3 border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs md:hidden dark:border-zinc-700"
        >
          文档
        </button>
        <h1 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
          AI 知识库问答
        </h1>
        <span className="text-xs text-zinc-400">Agent（多步检索）+ 固定 RAG 对照</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden w-[260px] shrink-0 md:block">
          <DocSidebar docs={docs} loading={docsLoading} onRefresh={refreshDocs} />
        </div>

        {drawerOpen && (
          <div className="fixed inset-0 z-20 flex md:hidden">
            <div className="w-[260px]">
              <DocSidebar docs={docs} loading={docsLoading} onRefresh={refreshDocs} />
            </div>
            <button
              type="button"
              aria-label="关闭文档栏"
              onClick={() => setDrawerOpen(false)}
              className="flex-1 bg-black/30"
            />
          </div>
        )}

        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-3 py-1.5 dark:border-zinc-800">
            <label className="text-xs text-zinc-500">模式</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as ChatMode)}
              disabled={running}
              aria-label="选择问答模式"
              data-testid="mode-select"
              className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            >
              <option value="agent">Agent（多步检索）</option>
              <option value="fast">快速问答</option>
            </select>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
            {messages.length === 0 ? (
              <p className="mt-8 text-center text-sm text-zinc-400">
                {noDocs ? "先上传文档，再开始提问" : "输入问题开始，例如「对比两份文档的结论」"}
              </p>
            ) : (
              <MessageList messages={messages} onJumpToSource={jumpToSource} />
            )}
            <div ref={bottomRef} />
          </div>

          <ChatInput disabled={noDocs} running={running} onSend={send} onStop={stop} />
        </main>
      </div>
    </div>
  );
}
