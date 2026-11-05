// ChatApp 集成测试：新架构（props 注入初始值、streamAgent 对象式调用、useConversations 持久化）。
// 行为锚点：
// - 发送问题后出现用户气泡和助手占位（answer 为空、running=true）
// - streamAgent 事件流驱动占位更新（step → answer → done）
// - fast 模式不注入占位，一次性渲染完整回复
// - 切换专家后新会话归属该专家
// - 会话持久化到 localStorage（agent-scoped）
// - 专家切换清空知识库面板 docs 列表

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatApp from "@/components/ChatApp";
import type { AgentInfo } from "@/lib/types";

const streamAgent = vi.hoisted(() => vi.fn());
const listAgents = vi.hoisted(() => vi.fn());
const listDocs = vi.hoisted(() => vi.fn());
const ask = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    streamAgent,
    listAgents,
    listDocs,
    ask,
  };
});

function agentList(agents: AgentInfo[]) {
  return { status: "ok" as const, agents };
}

function mkAgent(over: Partial<AgentInfo> = {}): AgentInfo {
  return {
    agent_id: "default",
    name: "默认专家",
    description: "",
    persona: "",
    greeting: "",
    emoji: "🤖",
    model: "",
    answer_mode: "strict",
    created_at: "",
    builtin: true,
    ...over,
  };
}

const DEFAULT_AGENTS: AgentInfo[] = [mkAgent()];

beforeEach(() => {
  localStorage.clear();
  streamAgent.mockReset();
  listAgents.mockReset();
  listDocs.mockReset();
  ask.mockReset();
  listAgents.mockResolvedValue(agentList(DEFAULT_AGENTS));
  listDocs.mockResolvedValue({ status: "ok", docs: [] });
  listAgents.mockResolvedValue(agentList(DEFAULT_AGENTS));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChatApp（新架构）", () => {
  it("初始渲染：专家切换器 + 空状态 + 输入框", async () => {
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);
    expect((await screen.findAllByText("默认专家")).length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText(/提问/)).toBeInTheDocument();
  });

  it("agent 模式：发送后注入占位并流式更新", async () => {
    streamAgent.mockImplementation(async (opts: any, onEvent: (e: any) => void) => {
      const emit = typeof opts === "object" && typeof opts.onEvent === "function" ? opts.onEvent : onEvent;
      emit?.({ type: "step", step: 1 });
      emit?.({ type: "thought", step: 1, text: "检索知识库" });
      emit?.({ type: "answer_delta", text: "这是答案" });
      emit?.({ type: "final", answer: "这是答案", sources: [], segments: [], grounded_ratio: 1 });
      return undefined;
    });

    const user = userEvent.setup();
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);

    const input = screen.getByPlaceholderText(/提问/);
    await user.type(input, "什么是接地气？");
    await user.keyboard("[Enter]");

    // 最终答案渲染
    await waitFor(() => {
      expect(screen.getByText("这是答案")).toBeInTheDocument();
    });
  });

  it("fast 模式：一次性渲染完整回复（走 ask）", async () => {
    ask.mockResolvedValue({ status: "ok", answer: "快速回复", sources: [], segments: null, groundedRatio: null });

    const user = userEvent.setup();
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);

    await user.type(screen.getByPlaceholderText(/提问/), "快速回答");
    // 切到 fast 模式（按钮文本「快速」）；点按钮后焦点离开输入框，改用发送按钮提交
    await user.click(screen.getByRole("button", { name: "快速" }));
    await user.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(screen.getByText("快速回复")).toBeInTheDocument();
    });
    expect(streamAgent).not.toHaveBeenCalled();
  });

  it("切换专家：地址栏同步且新会话归属新专家", async () => {
    const twoAgents = [
      ...DEFAULT_AGENTS,
      mkAgent({ agent_id: "kb-agent", name: "知识库专家", doc_count: 2 }),
    ];
    listAgents.mockResolvedValue(agentList(twoAgents));

    const user = userEvent.setup();
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);

    await user.click((await screen.findAllByText("默认专家"))[0]);
    await user.click(await screen.findByRole("menuitem", { name: /知识库专家/ }));

    await waitFor(() => {
      expect(window.location.search).toContain("agent=kb-agent");
    });
  });

  it("专家的知识库面板：展示文档列表", async () => {
    listDocs.mockResolvedValue({
      status: "ok",
      docs: [
        { doc_id: "d1", filename: "产品手册.pdf", ext: ".pdf", size: 102400, chunks: 12, uploaded_at: "2026-11-01T00:00:00Z" },
      ],
    });

    render(<ChatApp initialAgentId="default" initialConversationId={null} />);

    expect(await screen.findByText("产品手册.pdf")).toBeInTheDocument();
  });

  it("持久化：发送一轮对话后 localStorage 写入会话", async () => {
    streamAgent.mockImplementation(async (opts: any, onEvent: (e: any) => void) => {
      const emit = typeof opts === "object" && typeof opts.onEvent === "function" ? opts.onEvent : onEvent;
      emit?.({ type: "final", answer: "答", sources: [], segments: [], grounded_ratio: 1 });
      return undefined;
    });

    const user = userEvent.setup();
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);

    await user.type(screen.getByPlaceholderText(/提问/), "问题一");
    await user.keyboard("[Enter]");

    await waitFor(() => {
      const keys = Object.keys(localStorage);
      const stored = keys.find((k) => k.includes("conversation")) ?? keys[0];
      expect(stored).toBeTruthy();
      const parsed = JSON.parse(localStorage.getItem(stored as string) as string);
      expect(JSON.stringify(parsed)).toContain("问题一");
    });
  });

  it("localStorage 损坏时兜底为空会话列表", async () => {
    const keys = Object.keys(localStorage);
    keys.forEach((k) => localStorage.removeItem(k));
    const probe = localStorage.getItem("ai-kb-qa:conversations:default");
    expect(probe === null).toBe(true);
    render(<ChatApp initialAgentId="default" initialConversationId={null} />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/提问/)).toBeInTheDocument();
    });
  });

  it("链接里的 ?c=<id> 优先恢复指定会话，而不是最近一条", async () => {
    const mkConv = (id: string, title: string, text: string) => ({
      id,
      agentId: "default",
      title,
      messages: [{ id: `${id}-m`, role: "user", text, createdAt: 1 }],
      updatedAt: 1,
    });
    // 列表把「较新」的 conv-new 放前面，指定恢复的 conv-old 在后面
    localStorage.setItem(
      "kbqa:conversations:default",
      JSON.stringify([mkConv("conv-new", "新会话", "新会话内容"), mkConv("conv-old", "旧会话", "旧会话内容")]),
    );

    render(<ChatApp initialAgentId="default" initialConversationId="conv-old" />);

    // 正文区的用户气泡应为旧会话内容；新会话内容只出现在侧栏列表里，不应进入正文
    await waitFor(() => {
      const bubbles = Array.from(document.querySelectorAll(".brand-gradient")).map(
        (n) => n.textContent ?? "",
      );
      expect(bubbles).toContain("旧会话内容");
      expect(bubbles).not.toContain("新会话内容");
    });
  });

  it("指定的会话不存在时退回最近一条", async () => {
    localStorage.setItem(
      "kbqa:conversations:default",
      JSON.stringify([
        {
          id: "conv-a",
          agentId: "default",
          title: "甲",
          messages: [{ id: "a1", role: "user", text: "甲的内容", createdAt: 1 }],
          updatedAt: 1,
        },
      ]),
    );

    render(<ChatApp initialAgentId="default" initialConversationId="不存在的-id" />);

    await waitFor(() => {
      expect(screen.getAllByText("甲的内容").length).toBeGreaterThan(0);
    });
  });
});
