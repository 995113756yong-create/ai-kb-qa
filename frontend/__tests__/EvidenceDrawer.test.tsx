import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidenceDrawer } from "@/components/workspace/EvidenceDrawer";
import { clearDocContentCache } from "@/hooks/useDocContent";
import type { ChatMessage } from "@/lib/chat";
import type { DocContent, Source } from "@/lib/types";

// 移动端抽屉：底部滑出、复用阅读器、关闭回传 onOpenChange。

const PAGE_TEXT = "产品 A 的月费是 30 元。";
const DOC: DocContent = {
  status: "ok",
  doc_id: "d0",
  filename: "产品A.txt",
  precise: true,
  truncated: false,
  pages: [{ page: null, text: PAGE_TEXT }],
  chunks: [
    { chunk_id: "d0:0", chunk_index: 0, page: null, page_index: 0, start: 0, end: PAGE_TEXT.length },
  ],
};

const SOURCES: Source[] = [
  { index: 1, doc_id: "d0", source: "产品A.txt", page: null, snippet: PAGE_TEXT, chunk_id: "d0:0" },
];

function mkMessage(): ChatMessage & { role: "assistant" } {
  return {
    id: "a1",
    role: "assistant",
    mode: "agent",
    steps: [],
    answer: "产品 A 的月费是 30 元。[1]",
    sources: SOURCES,
    segments: [{ text: "产品 A 的月费是 30 元。", kind: "kb", citations: [1], warnings: [] }],
    groundedRatio: 1,
    answerMode: null,
    elapsedMs: 10,
    phase: "done",
    question: "",
    feedback: null,
    createdAt: 1,
  } as unknown as ChatMessage & { role: "assistant" };
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearDocContentCache();
  vi.restoreAllMocks();
});

describe("EvidenceDrawer", () => {
  it("打开时渲染抽屉与阅读器内容", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => DOC }),
    );

    render(
      <EvidenceDrawer open onOpenChange={() => {}} message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );

    expect(screen.getByTestId("evidence-drawer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("reader-text")).toBeInTheDocument();
    });
  });

  it("点关闭按钮时 onOpenChange(false) 被调用", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => DOC }),
    );
    const onOpenChange = vi.fn();

    render(
      <EvidenceDrawer open onOpenChange={onOpenChange} message={mkMessage()} n={1} agentId="default" onSelect={() => {}} onClose={() => {}} />,
    );

    await userEvent.click(screen.getByLabelText("关闭证据抽屉"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
