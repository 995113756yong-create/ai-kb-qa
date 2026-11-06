"use client";

// 证据阅读器：显示原文，高亮被引用的片段，可切换上一条/下一条证据。
// 桌面端是右侧栏，移动端由外层用底部抽屉承载（同一个组件）。
//
// 约定：全链路传引用编号 n（从 1 开始），取证据一律用 sourceByCitation。

import { useEffect, useMemo, useRef } from "react";
import { ChevronLeft, ChevronRight, FileText, X } from "lucide-react";

import { useDocContent } from "@/hooks/useDocContent";
import type { ChatMessage } from "@/lib/chat";
import { sourceByCitation } from "@/lib/citations";
import { splitByRanges, type Range } from "@/lib/highlight";
import type { Segment } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export type EvidenceReaderProps = {
  message: ChatMessage & { role: "assistant" };
  /** 当前引用编号 n（从 1 开始） */
  n: number;
  agentId: string;
  onSelect: (n: number) => void;
  onClose: () => void;
  /** 点击「被引用于」里的句子，让对话区滚动态该句并闪烁 */
  onFocusSentence?: (segmentIndex: number) => void;
  className?: string;
};

function Skeleton() {
  const widths = ["100%", "92%", "96%", "88%", "94%", "60%"];
  return (
    <div className="flex flex-col gap-2 p-4" data-testid="reader-skeleton">
      {widths.map((w, i) => (
        <div key={i} className="h-3 animate-pulse rounded bg-muted" style={{ width: w }} />
      ))}
    </div>
  );
}

export function EvidenceReader({
  message,
  n,
  agentId,
  onSelect,
  onClose,
  onFocusSentence,
  className,
}: EvidenceReaderProps) {
  const { t } = useI18n();
  const sources = useMemo(() => message.sources ?? [], [message.sources]);
  const total = sources.length;
  const source = sourceByCitation(sources, n);
  const { data, loading, error, retry } = useDocContent(agentId, source?.doc_id);

  const activeRef = useRef<HTMLElement | null>(null);

  // 当前证据所在页
  const activeChunk = useMemo(() => {
    if (!data || !source?.chunk_id) return null;
    return data.chunks.find((c) => c.chunk_id === source.chunk_id) ?? null;
  }, [data, source]);

  // 本条回答引用的其他编号在本页的区间
  const ranges: Range[] = useMemo(() => {
    if (!data || !activeChunk) return [];
    const pageIdx = activeChunk.page_index;
    const out: Range[] = [];
    for (const s of sources) {
      const c = data.chunks.find((x) => x.chunk_id === s.chunk_id);
      if (!c || c.page_index !== pageIdx) continue;
      out.push({ start: c.start, end: c.end, n: s.index, active: s.index === n });
    }
    return out;
  }, [data, activeChunk, sources, n]);

  // 打开或切换证据时，把当前高亮滚到视野中央
  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    el.classList.remove("evidence-breathe");
    // 触发一次呼吸动画
    void el.offsetWidth;
    el.classList.add("evidence-breathe");
  }, [n, activeChunk?.chunk_id]);

  // 快捷键：[ 上一条 ] 下一条 Esc 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (typing) return;
      if (e.key === "Escape") onClose();
      else if (e.key === "[") onSelect(Math.max(1, n - 1));
      else if (e.key === "]") onSelect(Math.min(total, n + 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [n, total, onSelect, onClose]);

  // 「被引用于」：本条回答里引用了当前 n 的句子
  const citedSegments = useMemo(() => {
    const segs = message.segments ?? [];
    const out: { index: number; seg: Segment }[] = [];
    segs.forEach((seg, i) => {
      if ((seg.citations ?? []).includes(n)) out.push({ index: i, seg });
    });
    return out;
  }, [message.segments, n]);

  if (!source) {
    return (
      <aside className={cn("flex items-center justify-center p-6 text-sm text-muted-foreground", className)}>
        {t("evidence.noSource")}
      </aside>
    );
  }

  const pageIdx = activeChunk?.page_index ?? 0;
  const pageText = data?.pages?.[pageIdx]?.text ?? "";

  return (
    <aside
      role="complementary"
      aria-label={t("evidence.title")}
      data-testid="evidence-reader"
      className={cn("flex h-full min-h-0 flex-col bg-card", className)}
    >
      {/* 头部 */}
      <header className="sticky top-0 z-10 shrink-0 border-b border-border/60 bg-card/95 px-3 py-2 backdrop-blur">
        <div className="flex items-center gap-1.5 text-sm">
          <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <span className="truncate font-medium" title={source.source ?? undefined}>
            {source.source ?? t("common.unknownDoc")}
          </span>
          {source.page !== null && source.page !== undefined ? (
            <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {t("common.page", { n: source.page })}
            </span>
          ) : null}
        </div>
        <div className="mt-1 flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <button
              type="button"
              onClick={() => onSelect(Math.max(1, n - 1))}
              disabled={n <= 1}
              aria-label={t("evidence.prev")}
              className="rounded p-0.5 hover:bg-muted disabled:opacity-30"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span data-testid="reader-counter">
              {t("evidence.counter", { n, total })}
            </span>
            <button
              type="button"
              onClick={() => onSelect(Math.min(total, n + 1))}
              disabled={n >= total}
              aria-label={t("evidence.next")}
              className="rounded p-0.5 hover:bg-muted disabled:opacity-30"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("evidence.close")}
            className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* 原文正文 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {loading ? <Skeleton /> : null}

        {error ? (
          <div className="flex flex-col items-start gap-2 p-2 text-xs">
            <p className="text-destructive">{error}</p>
            <button
              type="button"
              onClick={retry}
              className="rounded border border-border px-2 py-1 hover:bg-muted"
            >
              {t("common.retry")}
            </button>
          </div>
        ) : null}

        {!loading && !error && data?.precise === false ? (
          <p className="mb-2 rounded bg-info-bg px-2 py-1.5 text-[11px] text-muted-foreground">
            {t("evidence.legacyNotice")}
          </p>
        ) : null}

        {!loading && !error && data?.truncated && !activeChunk ? (
          <p className="mb-2 rounded bg-info-bg px-2 py-1.5 text-[11px] text-muted-foreground">
            {t("evidence.truncatedNotice")}
          </p>
        ) : null}

        {!loading && !error && data && activeChunk ? (
          <div className="whitespace-pre-wrap text-[13.5px] leading-7 text-foreground" data-testid="reader-text">
            {splitByRanges(pageText, ranges).map((slice, i) => {
              if (slice.ns.length === 0) return <span key={i}>{slice.text}</span>;
              const isActive = slice.active;
              return (
                <mark
                  key={i}
                  ref={isActive ? (el) => { activeRef.current = el; } : undefined}
                  {...(isActive ? { "data-active": "" } : { "data-other": "" })}
                  {...(isActive ? { "data-testid": "reader-active-mark" } : {})}
                >
                  {slice.text}
                  {slice.ns.map((num) => (
                    <span
                      key={num}
                      className="ml-0.5 align-super text-[9px] text-muted-foreground"
                      aria-hidden
                    >
                      {num}
                    </span>
                  ))}
                </mark>
              );
            })}
          </div>
        ) : null}

        {!loading && !error && data && !activeChunk ? (
          // 降级 / 截断时退回 snippet
          <blockquote className="whitespace-pre-wrap rounded bg-muted/50 p-2 text-[13px] leading-6">
            {source.snippet}
          </blockquote>
        ) : null}
      </div>

      {/* 被引用于 */}
      {citedSegments.length > 0 && onFocusSentence ? (
        <section className="shrink-0 border-t border-border/60 px-3 py-2">
          <p className="mb-1 text-[11px] font-medium text-muted-foreground">
            {t("evidence.citedIn", { n: citedSegments.length })}
          </p>
          <ul className="flex max-h-32 flex-col gap-1 overflow-y-auto">
            {citedSegments.map(({ index, seg }) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onFocusSentence(index)}
                  className="w-full rounded px-1.5 py-1 text-left text-[11px] leading-relaxed text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {seg.text.length > 60 ? `${seg.text.slice(0, 60)}…` : seg.text}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </aside>
  );
}

export default EvidenceReader;
