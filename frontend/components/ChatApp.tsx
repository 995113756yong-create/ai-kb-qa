"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ChatInput from "@/components/ChatInput";
import DocSidebar from "@/components/DocSidebar";
import MessageList from "@/components/MessageList";
import { ApiError, ask, listAgents, listDocs, streamAgent } from "@/lib/api";
import type { ChatMessage, Step } from "@/lib/chat";
import { stripRawCitations } from "@/lib/answer";
import type { AgentEvent, AgentInfo, ChatMode, DocInfo } from "@/lib/types";

let messageSeq = 0;
function nextId(prefix: string): string {
  messageSeq += 1;
  return `${prefix}-${messageSeq}`;
}

const DEFAULT_AGENT_ID = "default";

export default function ChatApp() {
  // 多专家平台状态
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [activeAgentId, setActiveAgentId] = useState<string>(DEFAULT_AGENT_ID);

  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<ChatMode>("agent");
  const [running, setRunning] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeAgent = agents.find((a) => a.agent_id === activeAgentId);

  const refreshAgents = useCallback(async () => {
    try {
      const data = await listAgents();
      setAgents(data.agents);
    } catch {
      // 专家列表读不到（无 Key 环境 / 后端不可用）保持空态
      setAgents([]);
    }
  }, []);

  const refreshDocs = useCallback(async () => {
    try {
      const data = await listDocs(activeAgentId);
      setDocs(data.docs);
    } catch {
      setDocs([]);
    } finally {
      setDocsLoading(false);
    }
  }, [activeAgentId]);

  // 首屏拉专家列表
  useEffect(() => {
    let alive = true;

    void listAgents()
      .then((data) => {
        if (alive) {
          setAgents(data.agents);
        }
      })
      .catch(() => {
        if (alive) {
          setAgents([]);
        }
      });

    return () => {
      alive = false;
    };
  }, []);

  // 切换专家：拉取该专家的文档，清空消息（跨专家保留消息会让引用错位）
  useEffect(() => {
    let alive = true;

    void listDocs(activeAgentId)
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
  }, [activeAgentId]);

  const selectAgent = useCallback((agentId: string) => {
    // 生成进行中切专家：先中止
    abortRef.current?.abort();
    abortRef.current = null;
    setActiveAgentId(agentId);
    setMessages([]);
    setDrawerOpen(false);
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
          case "decompose":
            return {
              ...message,
              steps: [
                ...message.steps,
                { kind: "decompose", key: `${id}-d`, queries: event.queries },
              ],
            };
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
              segments: event.segments ?? null,
              groundedRatio: event.grounded_ratio ?? null,
              answerMode: event.mode ?? null,
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
        stopped: false,
        error: null,
        elapsedMs: null,
        segments: null,
        groundedRatio: null,
        answerMode: null,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setRunning(true);
      setDrawerOpen(false);

      if (mode === "fast") {
        try {
          const result = await ask(text, activeAgentId);
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
        await streamAgent(
          text,
          (event) => handleAgentEvent(assistantId, event),
          controller.signal,
          activeAgentId,
        );
      } catch (e) {
        // 用户点“停止”会中断 fetch，这里不当作错误
        if (controller.signal.aborted) {
          patchMessage(assistantId, (m) =>
            m.role === "assistant"
              ? {
                  ...m,
                  // 没收到 final，正文里是模型原话的 [E3]，清掉以免显示无法点击的编号
                  answer: stripRawCitations(m.answer),
                  running: false,
                  stopped: true,
                }
              : m,
          );
        } else {
          const detail = e instanceof ApiError ? e.message : "连接中断，请重试";
          patchMessage(assistantId, (m) =>
            m.role === "assistant"
              ? { ...m, answer: stripRawCitations(m.answer), error: detail, running: false }
              : m,
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
    [activeAgentId, handleAgentEvent, mode, patchMessage],
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
  const emptyHint = noDocs
    ? `${activeAgent?.name ?? "当前专家"}还没有知识库文档，先在左侧上传`
    : "输入问题开始，例如「对比两份文档的结论」";

  return (
    <div className="flex h-full min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="flex items-center gap-3 border-b border-zinc-200/70 bg-white/80 px-4 py-2.5 backdrop-blur-sm dark:border-zinc-800/70 dark:bg-zinc-950/80">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600 transition-colors hover:bg-zinc-100 md:hidden dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          专家 / 文档
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-100 text-sm dark:bg-zinc-800" aria-hidden>
            {activeAgent?.emoji || "🤖"}
          </span>
          <div className="leading-tight">
            <h1 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
              {activeAgent?.name ?? "通用助手"}
            </h1>
            <p className="text-[11px] text-zinc-400">
              {activeAgent?.description || "Agent 多步检索 · 证据引用 · 流式输出"}
            </p>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden w-[280px] shrink-0 md:block">
          <DocSidebar
            agents={agents}
            activeAgentId={activeAgentId}
            docs={docs}
            docsLoading={docsLoading}
            onRefreshDocs={refreshDocs}
            onRefreshAgents={refreshAgents}
            onSelectAgent={selectAgent}
          />
        </div>

        {drawerOpen && (
          <div className="fixed inset-0 z-20 flex md:hidden">
            <div className="w-[280px]">
              <DocSidebar
                agents={agents}
                activeAgentId={activeAgentId}
                docs={docs}
                docsLoading={docsLoading}
                onRefreshDocs={refreshDocs}
                onRefreshAgents={refreshAgents}
                onSelectAgent={selectAgent}
              />
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
          <div className="flex items-center gap-2 border-b border-zinc-100 bg-white/60 px-3 py-1.5 dark:border-zinc-800/60 dark:bg-zinc-950/40">
            <label className="text-xs text-zinc-500">模式</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as ChatMode)}
              disabled={running}
              aria-label="选择问答模式"
              data-testid="mode-select"
              className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 outline-none transition-colors focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            >
              <option value="agent">Agent（多步检索）</option>
              <option value="fast">快速问答</option>
            </select>
          </div>

          <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-4">
            {messages.length === 0 ? (
              <div className="mt-16 flex flex-col items-center gap-3 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-100 text-2xl shadow-sm dark:bg-zinc-800">
                  {activeAgent?.emoji || "💬"}
                </span>
                {activeAgent?.greeting ? (
                  <p className="max-w-md rounded-2xl rounded-tl-md bg-white px-4 py-3 text-sm leading-relaxed text-zinc-600 shadow-sm dark:bg-zinc-900 dark:text-zinc-300">
                    {activeAgent.greeting}
                  </p>
                ) : (
                  <p className="text-sm text-zinc-400">{emptyHint}</p>
                )}
              </div>
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
