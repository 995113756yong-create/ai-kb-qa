"use client";

// 证据面板：回答右侧（移动端在下方）的证据视图。
// 按 source 切换标签，命中片段高亮，可折叠展开上下文。

import { useEffect, useState } from "react";

import { getChunk } from "@/lib/api";
import type { ChatMessage } from "@/lib/chat";
import { cn } from "@/lib/utils";

export type EvidencePanelProps = {
  message: ChatMessage & { role: "assistant" };
  /** 当前选中的证据编号（sources 数组下标），null 表示未选 */
  index: number | null;
  /** 当前专家 ID，展开上下文查 chunk 用 */
  agentId: string;
  onClose: () => void;
  className?: string;
};

export function EvidencePanel({ message, index, agentId, onClose, className }: EvidencePanelProps) {
  const sources = message.sources ?? [];
  const source = index !== null ? sources[index] : null;

  const [chunkText, setChunkText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 切换引用条目时清空上一次的正文。用「上一次的 index」判断是否真的换了条目，
  // 避免 effect 里无条件 setState（react-hooks/set-state-in-effect）。
  const [prevIndex, setPrevIndex] = useState(index);
  if (index !== prevIndex) {
    setPrevIndex(index);
    setChunkText(null);
    setError(null);
  }

  // Esc 关闭面板（方案 6.11）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (index === null || !source) {
    return (
      <div className={cn("flex items-center justify-center rounded-xl border border-dashed p-6 text-sm text-muted-foreground", className)}>
        点击回答中的引用编号查看证据原文
      </div>
    );
  }

  const hits = (message.steps ?? [])
    .filter((s): s is Extract<typeof s, { kind: "tool_result" }> => s.kind === "tool_result" && s.ok)
    .flatMap((s) => s.hits ?? []);

  const loadChunk = async () => {
    if (loading || !source?.chunk_id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getChunk(source.chunk_id, agentId);
      setChunkText(res.text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <aside
      data-testid="evidence-panel"
      className={cn("flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm", className)}
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-medium">
          证据 {source.index + 1}
          {source.source ? <span className="ml-2 text-muted-foreground">{source.source}</span> : null}
        </h3>
        <button type="button" onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground" aria-label="关闭证据面板">
          Esc ✕
        </button>
      </header>

      <div className="text-xs text-muted-foreground">
        {source.doc_id ? <span>文档 {source.doc_id}</span> : null}
        {source.page !== null && source.page !== undefined ? <span> · 第 {source.page} 页</span> : null}
      </div>

      <blockquote className="rounded-lg bg-muted/50 p-3 text-sm leading-relaxed">
        <p className="mb-1 text-[11px] font-medium uppercase text-muted-foreground">引用片段</p>
        {source.snippet}
      </blockquote>

      {hits.length > 0 ? (
        <section>
          <p className="mb-2 text-[11px] font-medium uppercase text-muted-foreground">检索命中（{hits.length}）</p>
          <ul className="flex max-h-52 flex-col gap-2 overflow-y-auto">
            {hits.slice(0, 8).map((hit, i) => (
              <li key={`${hit.chunk_id}-${i}`} className="rounded-md border bg-background p-2 text-xs leading-relaxed">
                <span className="mb-1 block font-medium">{hit.filename ?? hit.doc_id ?? "未知文档"}</span>
                {hit.text.slice(0, 160)}
                {hit.text.length > 160 ? "…" : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {chunkText ? (
        <blockquote className="rounded-lg border bg-background p-3 text-sm leading-relaxed">
          <p className="mb-1 text-[11px] font-medium uppercase text-muted-foreground">上下文</p>
          {chunkText}
        </blockquote>
      ) : (
        <button
          type="button"
          onClick={() => void loadChunk()}
          disabled={loading || !source.chunk_id}
          className="self-start rounded-md border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
        >
          {loading ? "加载中…" : "展开上下文"}
        </button>
      )}

      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </aside>
  );
}
