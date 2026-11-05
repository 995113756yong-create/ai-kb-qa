// 停止生成测试：新事件协议（event.type + step 对象）+ props 注入初始值。
// 锚点：chat-input / send-button / stopped-hint / assistant-* / stripRawCitations。

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatApp from "@/components/ChatApp";
import { stripRawCitations } from "@/lib/answer";
import * as api from "@/lib/api";
import type { DocInfo } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    listAgents: vi.fn(),
    listDocs: vi.fn(),
    streamAgent: vi.fn(),
    ask: vi.fn(),
  };
});

const mocked = vi.mocked(api);

const DOC: DocInfo = {
  doc_id: "a".repeat(32),
  filename: "产品A.txt",
  ext: ".txt",
  size: 128,
  chunks: 2,
  uploaded_at: "2026-10-27T09:00:00+00:00",
};

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  mocked.listAgents.mockResolvedValue({
    status: "ok",
    agents: [
      {
        agent_id: "default",
        name: "通用助手",
        description: "",
        persona: "",
        greeting: "",
        emoji: "🤖",
        model: "",
        answer_mode: "strict",
        created_at: "",
        builtin: true,
      },
    ],
  });
  mocked.listDocs.mockResolvedValue({ status: "ok", docs: [DOC] });
});

describe("stripRawCitations", () => {
  it("清掉未映射的 E 编号", () => {
    expect(stripRawCitations("苹果是水果 [E1]，香蕉 [E2]。")).toBe("苹果是水果，香蕉。");
  });

  it("支持全角括号、空格与范围写法", () => {
    expect(stripRawCitations("甲【E1】乙[ E2 ]丙[E3-E5]")).toBe("甲乙丙");
  });

  it("不误伤已映射的普通编号", () => {
    expect(stripRawCitations("价格表 [1] 与年份 [2024]")).toBe("价格表 [1] 与年份 [2024]");
  });

  it("压缩删除后残留的多余空格", () => {
    expect(stripRawCitations("结论 [E3]  ,  下一句")).toBe("结论, 下一句");
  });
});

describe("停止生成", () => {
  it("点停止后清掉原始编号并显示已停止", async () => {
    // mock 收到 abort 信号后才抛错，模拟真实的 fetch 中断时序
    mocked.streamAgent.mockImplementation((async (opts: any, onEvent, positionalSignal) => {
      // streamAgent 支持对象式与位置参数两种调用，优先取对象里的字段
      const emit = typeof opts?.onEvent === "function" ? opts.onEvent : onEvent;
      const signal = opts?.signal ?? positionalSignal;
      emit?.({ type: "step", step: 1 });
      emit?.({ type: "thought", step: 1, text: "检索知识库" });
      emit?.({ type: "answer_delta", text: "苹果是水果 [E1]，" });
      emit?.({ type: "answer_delta", text: "香蕉 [E2]。" });

      await new Promise<void>((resolve, reject) => {
        if (signal?.aborted) {
          reject(new DOMException("aborted", "AbortError"));
          return;
        }
        signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
        // 兜底，避免测试挂住
        setTimeout(resolve, 3000);
      });
    }) as typeof api.streamAgent);

    render(<ChatApp initialAgentId="default" initialConversationId={null} />);
    await screen.findByTestId("chat-input");

    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));

    // 等回答开始流式输出后点停止
    await vi.waitFor(() => expect(screen.getByTestId("send-button")).toHaveTextContent("停止"));
    await userEvent.click(screen.getByTestId("send-button"));

    await vi.waitFor(() => expect(screen.getByTestId("stopped-hint")).toBeInTheDocument());

    const article = document.querySelector('[data-testid^="assistant-"]');
    expect(article?.textContent).not.toContain("[E1]");
    expect(article?.textContent).not.toContain("[E2]");
    expect(screen.getByTestId("stopped-hint")).toHaveTextContent("已停止生成");
    // 停止后不该再显示"思考中…"
    expect(article?.textContent).not.toContain("思考中");
  });

  it("停止后不会误报错误", async () => {
    mocked.streamAgent.mockImplementation((async (opts: any, _onEvent, positionalSignal) => {
      const signal = opts?.signal ?? positionalSignal;
      await new Promise<void>((resolve, reject) => {
        signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
        setTimeout(resolve, 3000);
      });
    }) as typeof api.streamAgent);

    render(<ChatApp initialAgentId="default" initialConversationId={null} />);
    await screen.findByTestId("chat-input");

    await userEvent.type(screen.getByTestId("chat-input"), "苹果");
    await userEvent.click(screen.getByTestId("send-button"));
    await vi.waitFor(() => expect(screen.getByTestId("send-button")).toHaveTextContent("停止"));
    await userEvent.click(screen.getByTestId("send-button"));

    await vi.waitFor(() => expect(screen.getByTestId("stopped-hint")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
