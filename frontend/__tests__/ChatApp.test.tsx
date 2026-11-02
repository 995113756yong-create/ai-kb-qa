import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatApp from "@/components/ChatApp";
import * as api from "@/lib/api";
import type { AgentEvent, AgentInfo, DocInfo } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  listDocs: vi.fn(),
  uploadDoc: vi.fn(),
  deleteDoc: vi.fn(),
  ask: vi.fn(),
  streamAgent: vi.fn(),
  listAgents: vi.fn(),
  createAgent: vi.fn(),
  deleteAgent: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

const mocked = vi.mocked(api);

const DOC: DocInfo = {
  doc_id: "a".repeat(32),
  filename: "产品A.txt",
  ext: ".txt",
  size: 128,
  chunks: 2,
  uploaded_at: "2026-10-27T09:00:00+00:00",
};

const DEFAULT_AGENT: AgentInfo = {
  agent_id: "default",
  name: "通用助手",
  description: "基于上传文档回答任意领域的问题",
  persona: "",
  greeting: "",
  emoji: "🤖",
  model: "",
  created_at: "",
  builtin: true,
};

const FITNESS_AGENT: AgentInfo = {
  agent_id: "fitness-coach",
  name: "健身教练",
  description: "增肌减脂与跑步入门",
  persona: "你是健身教练",
  greeting: "你好！我是你的健身教练💪",
  emoji: "💪",
  model: "",
  created_at: "2026-11-01T00:00:00+00:00",
  builtin: false,
};

function agentList(agents: AgentInfo[]) {
  return { status: "ok" as const, agents };
}

function docList(docs: DocInfo[]) {
  return { status: "ok" as const, docs };
}

function emit(events: AgentEvent[]) {
  return async (
    _question: string,
    onEvent: (event: AgentEvent) => void,
  ): Promise<void> => {
    for (const event of events) {
      onEvent(event);
    }
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listAgents.mockResolvedValue(agentList([DEFAULT_AGENT]));
  mocked.listDocs.mockResolvedValue(docList([]));
  mocked.streamAgent.mockResolvedValue(undefined);
});

describe("ChatApp", () => {
  it("没有文档时输入框禁用并给出引导", async () => {
    render(<ChatApp />);

    await waitFor(() => expect(mocked.listDocs).toHaveBeenCalled());
    expect(screen.getByTestId("chat-input")).toBeDisabled();
    expect(screen.getByText(/先在左侧上传/)).toBeInTheDocument();
  });

  it("有文档时可以提问", async () => {
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    render(<ChatApp />);

    await waitFor(() => expect(screen.getByTestId("chat-input")).not.toBeDisabled());

    const input = screen.getByTestId("chat-input");
    await userEvent.type(input, "苹果是什么？");
    await userEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => expect(mocked.streamAgent).toHaveBeenCalledTimes(1));
    // default 专家：不传 agent_id 参数时走旧路径
    expect(mocked.streamAgent).toHaveBeenCalledWith("苹果是什么？", expect.any(Function), expect.anything(), "default");
  });

  it("Agent 模式渲染时间线、流式回答和出处卡片", async () => {
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    mocked.streamAgent.mockImplementation(
      emit([
        { type: "step", step: 1 },
        { type: "thought", step: 1, text: "先检索产品信息" },
        { type: "tool_call", step: 1, id: "c1", name: "search_kb", args: { query: "苹果" } },
        { type: "tool_result", step: 1, id: "c1", name: "search_kb", ok: true, summary: "命中 1 条" },
        {
          type: "answer_delta",
          text: "苹果是一种水果 [E1]",
        },
        {
          type: "final",
          answer: "苹果是一种水果 [1]",
          sources: [{ index: 1, doc_id: DOC.doc_id, source: "产品A.txt", page: 2, snippet: "苹果是一种水果" }],
          grounded: true,
          steps: 2,
          elapsed_ms: 4200,
        },
      ]),
    );

    render(<ChatApp />);
    await waitFor(() => expect(screen.getByTestId("chat-input")).not.toBeDisabled());

    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));

    // 完成后时间线自动折叠成一行摘要：检索次数 + 用时
    await waitFor(() => expect(screen.getByTestId("trace-toggle")).toHaveTextContent("用时 4.2s"));
    expect(screen.getByTestId("trace-toggle")).toHaveTextContent("检索 1 次");
    expect(screen.queryByTestId("trace-steps")).not.toBeInTheDocument();

    // 展开后能看到思考、工具调用和工具结果
    await userEvent.click(screen.getByTestId("trace-toggle"));
    await waitFor(() => expect(screen.getByTestId("trace-steps").lastChild).toBeInTheDocument());
    expect(screen.getByText(/先检索产品信息/)).toBeInTheDocument();
    expect(screen.getByText(/search_kb\(query=苹果\)/)).toBeInTheDocument();
    expect(screen.getByText(/命中 1 条/)).toBeInTheDocument();

    // 回答已替换成 final 的版本：原始 [E1] 消失，换成可点击的 [1]
    expect(screen.getByRole("button", { name: "查看出处 1" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("[E1]");

    // 出处卡片
    expect(screen.getByTestId("source-card-1")).toHaveTextContent("产品A.txt");
    expect(screen.getByTestId("source-card-1")).toHaveTextContent("第2页");
  });

  it("grounded=false 时显示黄色提示", async () => {
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    mocked.streamAgent.mockImplementation(
      emit([
        { type: "step", step: 1 },
        { type: "thought", step: 1, text: "直接作答" },
        { type: "answer_delta", text: "苹果是一种水果。" },
        {
          type: "final",
          answer: "苹果是一种水果。",
          sources: [],
          grounded: false,
          steps: 1,
          elapsed_ms: 900,
        },
      ]),
    );

    render(<ChatApp />);
    await waitFor(() => expect(screen.getByTestId("chat-input")).not.toBeDisabled());

    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));

    await waitFor(() =>
      expect(screen.getByTestId("ungrounded-warning")).toHaveTextContent(
        "该回答未引用文档内容，请谨慎参考",
      ),
    );
  });

  it("error 事件展示错误信息", async () => {
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    mocked.streamAgent.mockImplementation(
      emit([{ type: "step", step: 1 }, { type: "error", detail: "大模型调用失败：APIStatusError" }]),
    );

    render(<ChatApp />);
    await waitFor(() => expect(screen.getByTestId("chat-input")).not.toBeDisabled());

    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("大模型调用失败：APIStatusError"),
    );
  });

  it("快速问答模式调用 /api/ask 并展示出处", async () => {
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    mocked.ask.mockResolvedValue({
      status: "ok",
      question: "苹果",
      answer: "苹果是一种水果 [1]",
      sources: [{ index: 1, doc_id: DOC.doc_id, source: "产品A.txt", page: null, snippet: "苹果" }],
    });

    render(<ChatApp />);
    await waitFor(() => expect(screen.getByTestId("chat-input")).not.toBeDisabled());

    await userEvent.selectOptions(screen.getByTestId("mode-select"), "fast");
    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => expect(mocked.ask).toHaveBeenCalledWith("苹果", "default"));
    expect(mocked.streamAgent).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("source-card-1")).toBeInTheDocument());
  });
});

// ---------- 多专家平台 ----------

describe("多专家平台", () => {
  it("专家列表渲染，default 排第一且不可删除", async () => {
    mocked.listAgents.mockResolvedValue(agentList([DEFAULT_AGENT, FITNESS_AGENT]));
    render(<ChatApp />);

    await waitFor(() => expect(screen.getByTestId("agent-list").children.length).toBe(2));
    // default 在第一位
    expect(screen.getByTestId("agent-item-default")).toBeInTheDocument();
    expect(screen.getByTestId("agent-item-fitness-coach")).toBeInTheDocument();
    // default 没有删除按钮（builtin）
    expect(screen.queryByLabelText("删除专家 通用助手")).not.toBeInTheDocument();
    // 自定义专家有删除按钮
    expect(screen.getByLabelText("删除专家 健身教练")).toBeInTheDocument();
  });

  it("切换专家：拉取该专家文档，问答请求带 agent_id", async () => {
    mocked.listAgents.mockResolvedValue(agentList([DEFAULT_AGENT, FITNESS_AGENT]));
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    mocked.streamAgent.mockImplementation(emit([]));
    render(<ChatApp />);

    await waitFor(() => expect(screen.getByTestId("agent-item-fitness-coach")).toBeInTheDocument());
    // 初始拉的是 default 的文档
    await waitFor(() => expect(mocked.listDocs).toHaveBeenCalledWith("default"));

    await userEvent.click(screen.getByTestId("agent-item-fitness-coach"));

    // 切换后拉健身专家的文档
    await waitFor(() => expect(mocked.listDocs).toHaveBeenCalledWith("fitness-coach"));

    await userEvent.type(screen.getByTestId("chat-input"), "怎么练");
    await userEvent.click(screen.getByTestId("send-button"));

    await waitFor(() =>
      expect(mocked.streamAgent).toHaveBeenCalledWith("怎么练", expect.any(Function), expect.anything(), "fitness-coach"),
    );
  });

  it("新建专家：填表提交后刷新列表", async () => {
    mocked.listAgents.mockResolvedValue(agentList([DEFAULT_AGENT]));
    mocked.createAgent.mockResolvedValue({
      status: "ok",
      agent_id: "cooking",
      name: "烹饪助手",
    });

    render(<ChatApp />);
    await waitFor(() => expect(screen.getByTestId("create-agent-button")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("create-agent-button"));
    await waitFor(() => {
      expect(screen.getByTestId("create-agent-form")).toBeInTheDocument();
    });

    await userEvent.type(screen.getByTestId("agent-name-input"), "烹饪助手");
    await userEvent.type(screen.getByTestId("agent-persona-input"), "你是厨师");

    await userEvent.click(screen.getByTestId("agent-submit"));

    await waitFor(() => expect(mocked.createAgent).toHaveBeenCalled());
    expect(mocked.createAgent.mock.calls[0][0]).toMatchObject({
      name: "烹饪助手",
      persona: "你是厨师",
    });
    // 提交成功后重新拉列表
    await waitFor(() => expect(mocked.listAgents.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("专家 greeting 展示在空会话态", async () => {
    mocked.listAgents.mockResolvedValue(agentList([DEFAULT_AGENT, FITNESS_AGENT]));
    mocked.listDocs.mockResolvedValue(docList([DOC]));
    render(<ChatApp />);

    await waitFor(() => expect(screen.getByTestId("agent-item-fitness-coach")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("agent-item-fitness-coach"));

    // 健身专家的欢迎语展示在空会话处
    await waitFor(() => expect(screen.getByText(/健身教练💪/)).toBeInTheDocument());
  });
});
