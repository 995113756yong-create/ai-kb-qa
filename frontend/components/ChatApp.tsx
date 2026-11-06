"use client";

// 工作台主组件：会话状态编排 + 布局（左侧栏 + 主对话区）。
// 不使用 useSearchParams/useRouter，初始值经 props 注入（方案 6.5），
// 地址栏同步用 window.history.replaceState，避免组件测试 mock Next 路由。

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ChatInput from "@/components/ChatInput";
import CommandPalette from "@/components/CommandPalette";
import MessageList from "@/components/MessageList";
import AppSidebar from "@/components/workspace/AppSidebar";
import { AdminTokenDialog } from "@/components/workspace/AdminTokenDialog";
import { EvidencePanel } from "@/components/workspace/EvidencePanel";
import { toast } from "sonner";

import type { AskResponse, AgentInfo, AgentCreateRequest } from "@/lib/types";
import type { ChatMessage } from "@/lib/chat";
import { ask, listAgents, createAgent, deleteAgent } from "@/lib/api";
import { useAgentRun } from "@/lib/useAgentRun";
import { buildHistory } from "@/lib/history";
import { useConversations } from "@/lib/useConversations";
import { useDocs } from "@/hooks/useDocs";
import { useHotkeys, type HotkeyHandlers } from "@/hooks/useHotkeys";

type Props = {
  initialAgentId: string;
  initialConversationId: string | null;
};

export default function ChatApp({ initialAgentId, initialConversationId }: Props) {
  // ---------- 基础状态 ----------
  const [activeAgentId, setActiveAgentId] = useState(initialAgentId);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<"agent" | "fast">("agent");
  const [tokenOpen, setTokenOpen] = useState(false);
  // 用引用编号 n（从 1 开始），不用数组下标
  const [evidence, setEvidence] = useState<{ messageId: string; n: number } | null>(null);

  const activeAgent = useMemo(
    () => agents.find((a) => a.agent_id === activeAgentId) ?? null,
    [agents, activeAgentId],
  );
  const answerMode = activeAgent?.answer_mode ?? null;

  // ---------- Agent 列表 ----------
  // setState 都在 await 之后，不在 effect 同步阶段触发级联渲染
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listAgents();
        if (cancelled) return;
        setAgents(res.agents);
      } catch {
        if (cancelled) return;
        toast.error("加载专家列表失败");
      } finally {
        if (!cancelled) setAgentsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ---------- 会话管理 ----------
  const {
    conversations,
    current,
    currentId,
    setCurrentId,
    create,
    remove,
    rename,
    appendMessages,
    updateMessage,
    ensureTitle,
  } = useConversations(activeAgentId, initialConversationId);

  const messages = current?.messages ?? [];

  // ---------- 文档列表 ----------
  const {
    docs,
    loading: docsLoading,
    refresh: refreshDocs,
    upload,
    remove: removeDoc,
  } = useDocs(activeAgentId);

  // ---------- 地址栏同步 ----------
  const syncAddress = useCallback((agentId: string, conversationId: string | null) => {
    const params = new URLSearchParams();
    if (agentId && agentId !== "default") params.set("agent", agentId);
    if (conversationId) params.set("c", conversationId);
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `/?${qs}` : "/");
  }, []);

  // ---------- 专家管理 ----------
  const refreshAgents = useCallback(async () => {
    try {
      const res = await listAgents();
      setAgents(res.agents);
    } catch {
      toast.error("加载专家列表失败");
    }
  }, []);

  const handleCreateAgent = useCallback(
    async (payload: AgentCreateRequest) => {
      try {
        await createAgent(payload);
        toast.success(`专家「${payload.name}」创建成功`);
        await refreshAgents();
        await refreshDocs();
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "创建专家失败");
      }
    },
    [refreshAgents, refreshDocs],
  );

  const handleDeleteAgent = useCallback(
    async (agentId: string) => {
      try {
        await deleteAgent(agentId);
        toast.success("专家已删除");
        if (agentId === activeAgentId) {
          setActiveAgentId("default");
          syncAddress("default", null);
        }
        await refreshAgents();
        await refreshDocs();
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "删除专家失败");
      }
    },
    [activeAgentId, refreshAgents, refreshDocs, syncAddress],
  );

  useEffect(() => {
    syncAddress(activeAgentId, currentId);
  }, [activeAgentId, currentId, syncAddress]);

  // ---------- Agent 运行 ----------
  const { running, run, cancel } = useAgentRun();

  // 本轮运行的目标会话与占位消息 id。用 ref 而非 state：
  // run() 的回调只在启动时捕获一次，读 state 会拿到发送那一刻的旧值。
  const runTargetRef = useRef<{ convId: string; assistantId: string } | null>(null);

  const updateLast = useCallback(
    (updater: (m: ChatMessage & { role: "assistant" }) => ChatMessage) => {
      const target = runTargetRef.current;
      if (!target || !target.assistantId) return;
      updateMessage(target.convId, target.assistantId, (m) =>
        updater(m as ChatMessage & { role: "assistant" }),
      );
    },
    [updateMessage],
  );

  // ---------- 发送 ----------
  const send = useCallback(
    (question: string) => {
      if (!question.trim() || running) return;

      runTargetRef.current = null;
      let convId = currentId;
      if (!convId) convId = create();

      // 先取本轮之前的消息构造 history（appendMessages 之后取会把本轮问题算进去）
      const history = buildHistory(convId ? (conversations.find((c) => c.id === convId)?.messages ?? []) : []);

      ensureTitle(convId, question);
      appendMessages(convId, [{ id: `u-${Date.now()}`, role: "user", text: question, createdAt: Date.now() }]);
      setEvidence(null);

      if (mode === "fast") {
        // 快速问答：一次性 /api/ask，无时间线
        void ask(question, activeAgentId)
          .then((res: AskResponse) => {
            appendMessages(convId, [
              {
                id: `a-${Date.now()}`,
                role: "assistant",
                mode: "fast",
                steps: [],
                answer: res.answer,
                sources: res.sources,
                segments: null,
                groundedRatio: null,
                answerMode: null,
                running: false,
                stopped: false,
                error: null,
                elapsedMs: null,
                createdAt: Date.now(),
                phase: "done",
                question,
                feedback: null,
              },
            ]);
          })
          .catch((err: unknown) => {
            const detail = err instanceof Error ? err.message : String(err);
            appendMessages(convId, [
              {
                id: `a-${Date.now()}`,
                role: "assistant",
                mode: "fast",
                steps: [],
                answer: `获取回答失败：${detail}`,
                sources: null,
                segments: null,
                groundedRatio: null,
                answerMode: null,
                running: false,
                stopped: false,
                error: detail,
                elapsedMs: null,
                createdAt: Date.now(),
                phase: "done",
                question,
                feedback: null,
              },
            ]);
          });
        return;
      }

      // agent 交互模式：走流式时间线
      run({
        agentId: activeAgentId,
        question,
        mode: "agent",
        answerMode: answerMode ?? undefined,
        history,
        message: (msg) => {
          // run 注入完整 assistant 占位消息，追加进当前会话并登记为本轮更新目标
          if (convId) {
            runTargetRef.current = { convId, assistantId: msg.id };
            appendMessages(convId, [msg]);
          }
        },
        update: updateLast,
      });
    },
    [
      activeAgentId,
      answerMode,
      appendMessages,
      conversations,
      create,
      currentId,
      ensureTitle,
      mode,
      run,
      running,
      updateLast,
    ],
  );

  const stop = useCallback(() => {
    // 不清 runTargetRef：abort 后还要靠它把 stopped 状态写回这条消息
    cancel();
  }, [cancel]);

  const newChat = useCallback(() => {
    cancel();
    runTargetRef.current = null;
    create();
    setEvidence(null);
  }, [cancel, create]);

  const switchAgent = useCallback(
    (agentId: string) => {
      cancel();
      runTargetRef.current = null;
      setActiveAgentId(agentId);
      syncAddress(agentId, null);
    },
    [cancel, syncAddress],
  );

  const jumpToSource = useCallback((messageId: string, n: number) => {
    setEvidence({ messageId, n });
  }, []);

  // ---------- 快捷键 ----------
  const hotkeys: HotkeyHandlers = useMemo(
    () => ({
      onOpenPalette: () => window.dispatchEvent(new Event("kb:open-palette")),
      onToggleSidebar: () => setSidebarOpen((v) => !v),
      onEscape: () => setEvidence(null),
    }),
    [],
  );
  useHotkeys(hotkeys);

  // ---------- 渲染 ----------
  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background text-foreground">
      {/* 左侧栏 */}
      <div
        className={`${sidebarOpen ? "w-72" : "w-0"} shrink-0 overflow-hidden border-r border-border/60 transition-[width] duration-200 max-md:absolute max-md:z-40 max-md:h-full`}
      >
        <AppSidebar
          agents={agents}
          agentsLoading={agentsLoading}
          activeAgentId={activeAgentId}
          onSwitchAgent={switchAgent}
          conversations={conversations}
          currentId={currentId}
          onSelectConversation={setCurrentId}
          onNewChat={newChat}
          onDeleteConversation={remove}
          onRenameConversation={rename}
          docs={docs}
          docsLoading={docsLoading}
          onUpload={upload}
          onDeleteDoc={removeDoc}
          onCreateAgent={handleCreateAgent}
          onDeleteAgent={handleDeleteAgent}
          activeAgent={activeAgent ?? undefined}
        />
      </div>

      {/* 主区域 */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* 顶栏 */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border/60 px-4">
          <button
            type="button"
            aria-label="折叠侧栏"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={() => setSidebarOpen((v) => !v)}
          >
            ☰
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium leading-tight">
              {activeAgent?.name ?? "知识库问答"}
            </p>
            {activeAgent?.description && (
              <p className="truncate text-xs text-muted-foreground">{activeAgent.description}</p>
            )}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex rounded-lg border border-border/60 p-0.5" role="group" aria-label="交互模式">
              <button
                type="button"
                aria-pressed={mode === "agent"}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${mode === "agent" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
                onClick={() => setMode("agent")}
              >
                Agent
              </button>
              <button
                type="button"
                aria-pressed={mode === "fast"}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${mode === "fast" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
                onClick={() => setMode("fast")}
              >
                快速
              </button>
            </div>
            <button
              type="button"
              aria-label="新建会话"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={newChat}
            >
              ✚
            </button>
          </div>
        </header>

        {/* 消息区 */}
        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <MessageList messages={messages} onJumpToSource={jumpToSource} />
            {mode === "fast" && messages.length > 0 ? (
              <div className="flex items-center justify-center gap-1.5 border-t border-border/60 bg-muted/30 px-4 py-1.5 text-[11px] text-muted-foreground">
                快速模式不理解上下文，追问请切换到 Agent 模式
                <button
                  type="button"
                  onClick={() => setMode("agent")}
                  className="font-medium text-primary underline underline-offset-2"
                >
                  切换
                </button>
              </div>
            ) : null}
            <ChatInput disabled={false} running={running} onSend={send} onStop={stop} />
          </div>

          {/* 证据侧栏 */}
          {evidence && (() => {
            const evidenceMessage = messages.find(
              (m): m is ChatMessage & { role: "assistant" } => m.id === evidence.messageId && m.role === "assistant",
            );
            if (!evidenceMessage) return null;
            return (
              <aside className="hidden w-96 shrink-0 overflow-y-auto border-l border-border/60 lg:block">
                <EvidencePanel
                  message={evidenceMessage}
                  n={evidence.n}
                  agentId={activeAgentId}
                  onClose={() => setEvidence(null)}
                />
              </aside>
            );
          })()}
        </div>
      </main>

      {/* 命令面板（自管 open 状态，⌘K 打开） */}
      <CommandPalette
        workspace
        onNewConversation={newChat}
        onNewAgent={() => setTokenOpen(true)}
        onNavigate={(href) => {
          if (typeof window !== "undefined") window.location.assign(href);
        }}
      />

      {/* 管理员令牌对话框 */}
      <AdminTokenDialog
        open={tokenOpen}
        onSave={() => {
          setTokenOpen(false);
          void refreshDocs();
        }}
        onCancel={() => setTokenOpen(false)}
      />
    </div>
  );
}
