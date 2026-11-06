import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MessageActions } from "@/components/workspace/MessageActions";
import { countSegments, TrustSummary } from "@/components/workspace/TrustSummary";
import type { ChatMessage } from "@/lib/chat";
import type { Segment, Source } from "@/lib/types";

// 引用交互：可信度摘要计数与跳转、复制带出处的格式。

const SOURCES: Source[] = [
  { index: 1, doc_id: "d0", source: "产品A.txt", page: null, snippet: "A" },
  { index: 2, doc_id: "d1", source: "产品B.txt", page: 3, snippet: "B" },
];

function mkMessage(over: Partial<ChatMessage> = {}): ChatMessage & { role: "assistant" } {
  return {
    id: "a1",
    role: "assistant",
    mode: "agent",
    steps: [],
    answer: "产品 A 的月费是 30 元 [1][2]。",
    sources: SOURCES,
    segments: [
      { text: "句一", kind: "kb", citations: [1], warnings: [] },
      { text: "句二", kind: "kb", citations: [2], warnings: [] },
      { text: "句三", kind: "kb", citations: [1], warnings: [] },
      { text: "句四", kind: "general", citations: [], warnings: [] },
      { text: "句五", kind: "kb", citations: [1], warnings: ["数字 60 未出现在引用片段中"] },
    ] as Segment[],
    groundedRatio: 0.8,
    answerMode: null,
    elapsedMs: 100,
    phase: "done",
    question: "q",
    feedback: null,
    createdAt: 1,
    ...over,
  } as ChatMessage & { role: "assistant" };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("countSegments", () => {
  it("分别统计 kb / general / 带 warning 的句子数", () => {
    const c = countSegments(mkMessage());
    expect(c.kb).toBe(4);
    expect(c.general).toBe(1);
    expect(c.warn).toBe(1);
  });

  it("记录每类第一句的下标", () => {
    const c = countSegments(mkMessage());
    expect(c.firstKb).toBe(0);
    expect(c.firstGeneral).toBe(3);
    expect(c.firstWarn).toBe(4);
  });

  it("收集 warning 原文", () => {
    const c = countSegments(mkMessage());
    expect(c.warnings).toEqual(["数字 60 未出现在引用片段中"]);
  });
});

describe("TrustSummary", () => {
  it("grounded_ratio 为 null 时不渲染", () => {
    const { container } = render(<TrustSummary message={mkMessage({ groundedRatio: null })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("渲染百分比", () => {
    render(<TrustSummary message={mkMessage()} />);
    expect(screen.getByTestId("trust-summary").textContent).toContain("80%");
  });

  it("点「数字待核对」跳到对应句子", async () => {
    const onFocus = vi.fn();
    render(<TrustSummary message={mkMessage()} onFocusSegment={onFocus} />);

    await userEvent.click(screen.getByTestId("trust-summary"));
    const btn = await screen.findByText("数字待核对");
    await userEvent.click(btn);
    expect(onFocus).toHaveBeenCalledWith(4);
  });
});

describe("MessageActions 复制（带出处）", () => {
  it("生成的文本含正文与出处清单，且正文去掉引用编号", async () => {
    const written: string[] = [];
    Object.assign(navigator, {
      clipboard: { writeText: (s: string) => { written.push(s); return Promise.resolve(); } },
    });

    render(
      <MessageActions answer="产品 A 的月费是 30 元 [1][2]。" question="q" sources={SOURCES} />,
    );

    await userEvent.click(screen.getByTestId("copy-with-sources"));

    expect(written).toHaveLength(1);
    const txt = written[0];
    expect(txt).toContain("产品 A 的月费是 30 元。");
    // 正文里的引用编号被去掉；出处清单里仍保留 [n] 作为来源标识
    expect(txt.split("出处：")[0]).not.toContain("[1]");
    expect(txt).toContain("出处：");
    expect(txt).toContain("[1] 产品A.txt");
    expect(txt).toContain("[2] 产品B.txt 第 3 页");
  });

  it("没有 sources 时只复制正文", async () => {
    const written: string[] = [];
    Object.assign(navigator, {
      clipboard: { writeText: (s: string) => { written.push(s); return Promise.resolve(); } },
    });

    render(<MessageActions answer="纯回答 [1]。" question="q" sources={null} />);
    await userEvent.click(screen.getByTestId("copy-with-sources"));

    expect(written[0]).toBe("纯回答。");
    expect(written[0]).not.toContain("出处");
  });
});
