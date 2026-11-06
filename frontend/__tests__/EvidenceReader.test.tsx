import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidenceReader } from "@/components/workspace/EvidenceReader";
import { clearDocContentCache } from "@/hooks/useDocContent";
import type { ChatMessage } from "@/lib/chat";
import type { DocContent, Source } from "@/lib/types";

// 阅读器：显示原文、高亮当前片段、切换证据、Esc 关闭、被引用于点击。

const PAGE_TEXT = "产品 A 说明\n\n产品 A 的月费是 30 元，企业版 99 元。";

const CHUNKS = [
  { chunk_id: "d0:0", chunk_index: 0, page: null, page_index: 0, start: 0, end: 7 },
  { chunk_id: "d0:1", chunk_index: 1, page: null, page_index: 0, start: 9, end: 32 },
];

const DOC: DocContent = {
  status: "ok",
  doc_id: "d0",
  filename: "产品A.txt",
  precise: true,
  truncated: false,
  pages: [{ page: null, text: PAGE_TEXT }],
  chunks: CHUNKS,
};

const SOURCES: Source[] = [
  { index: 1, doc_id: "d0", source: "产品A.txt", page: null, snippet: "产品 A 说明", chunk_id: "d0:0" },
  { index: 2, doc_id: "d0", source: "产品A.txt", page: null, snippet: "月费", chunk_id: "d0:1" },
];

function mkMessage(over: Partial<ChatMessage> = {}): ChatMessage & { role: "assistant" } {
  return {
    id: "a1",
    role: "assistant",
    mode: "agent",
    steps: [],
    answer: "产品 A 的月费是 30 元。[1][2]",
    sources: SOURCES,
    segments: [
      { text: "产品 A 的月费是 30 元。", kind: "kb", citations: [1, 2], warnings: [] },
      { text: "以上仅供参考。", kind: "general", citations: [], warnings: [] },
    ],
    groundedRatio: 1,
    answerMode: null,
    elapsedMs: 100,
    phase: "done",
    question: "",
    feedback: null,
    createdAt: 1,
    ...over,
  } as ChatMessage & { role: "assistant" };
}

function mockContent(body: unknown) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearDocContentCache();
  vi.restoreAllMocks();
});

describe("EvidenceReader", () => {
  it("高亮区域文本等于 pages[page_index].text.slice(start, end)", async () => {
    mockContent(DOC);
    render(
      <EvidenceReader message={mkMessage()} n={2} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );

    const mark = await screen.findByTestId("reader-active-mark");
    expect(mark.textContent).toContain(PAGE_TEXT.slice(9, 32));
  });

  it("显示文件名与证据计数", async () => {
    mockContent(DOC);
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByText("产品A.txt")).toBeInTheDocument();
    });
    expect(screen.getByTestId("reader-counter").textContent).toContain("证据 1 / 2");
  });

  it("点下一条切换到 n+1，到最后一条时禁用", async () => {
    mockContent(DOC);
    const onSelect = vi.fn();
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={onSelect} onClose={() => {}} />,
    );

    await userEvent.click(screen.getByLabelText("下一条证据"));
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it("第一条时上一条按钮禁用", async () => {
    mockContent(DOC);
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );
    expect(screen.getByLabelText("上一条证据")).toBeDisabled();
  });

  it("按 Esc 触发 onClose", async () => {
    mockContent(DOC);
    const onClose = vi.fn();
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={onClose} />,
    );

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("按 ] 切到下一证据", async () => {
    mockContent(DOC);
    const onSelect = vi.fn();
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={onSelect} onClose={() => {}} />,
    );

    await userEvent.keyboard("]");
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it("在「被引用于」区点句子触发 onFocusSentence", async () => {
    mockContent(DOC);
    const onFocus = vi.fn();
    render(
      <EvidenceReader
        message={mkMessage()}
        n={1}
        agentId="default"
        onSelect={() => {}}
        onClose={() => {}}
        onFocusSentence={onFocus}
      />,
    );

    const btn = await screen.findByText(/产品 A 的月费是 30 元/);
    await userEvent.click(btn);
    expect(onFocus).toHaveBeenCalledWith(0);
  });

  it("precise=false 时显示降级提示", async () => {
    mockContent({ ...DOC, precise: false });
    render(
      <EvidenceReader message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/旧版本上传/)).toBeInTheDocument();
    });
  });

  it("引用没有对应证据时给出说明", () => {
    render(
      <EvidenceReader
        message={mkMessage({ sources: [] })}
        n={1}
        agentId="default"
        onSelect={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText(/没有对应的证据/)).toBeInTheDocument();
  });
});
