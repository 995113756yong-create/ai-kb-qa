"use client";

// 可信度摘要：环形图 + Popover 说明。
// 显示知识库依据 / 一般知识 / 数字待核对三类计数，每类可点击跳到对应句子。

import { useMemo } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ChatMessage } from "@/lib/chat";
import { cn } from "@/lib/utils";

export type TrustSummaryProps = {
  message: ChatMessage & { role: "assistant" };
  /** 点击某类句子时回调，传入该句在 segments 里的下标 */
  onFocusSegment?: (index: number) => void;
  className?: string;
};

type Counts = {
  kb: number;
  general: number;
  warn: number;
  firstKb: number | null;
  firstGeneral: number | null;
  firstWarn: number | null;
  warnings: string[];
};

export function countSegments(message: ChatMessage & { role: "assistant" }): Counts {
  const segs = message.segments ?? [];
  const out: Counts = {
    kb: 0,
    general: 0,
    warn: 0,
    firstKb: null,
    firstGeneral: null,
    firstWarn: null,
    warnings: [],
  };
  segs.forEach((s, i) => {
    if (s.kind === "kb") {
      out.kb += 1;
      if (out.firstKb === null) out.firstKb = i;
    } else if (s.kind === "general") {
      out.general += 1;
      if (out.firstGeneral === null) out.firstGeneral = i;
    }
    if (s.warnings.length > 0) {
      out.warn += 1;
      if (out.firstWarn === null) out.firstWarn = i;
      out.warnings.push(...s.warnings);
    }
  });
  return out;
}

export function TrustSummary({ message, onFocusSegment, className }: TrustSummaryProps) {
  const counts = useMemo(() => countSegments(message), [message]);
  const ratio = message.groundedRatio;

  // 严格模式拒答、闲聊时 grounded_ratio 为 null，不显示环形图
  if (ratio === null || ratio === undefined) return null;

  const pct = Math.round(ratio * 100);
  const r = 9;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;

  const rows = [
    { key: "kb", label: "知识库依据", n: counts.kb, idx: counts.firstKb, tone: "text-kb" },
    { key: "general", label: "一般知识", n: counts.general, idx: counts.firstGeneral, tone: "text-general" },
    { key: "warn", label: "数字待核对", n: counts.warn, idx: counts.firstWarn, tone: "text-warn" },
  ];

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="trust-summary"
          className={cn(
            "inline-flex items-center gap-1 rounded-full border border-border/60 px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted",
            className,
          )}
          aria-label={`知识库依据 ${pct}%`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden>
            <circle cx="12" cy="12" r={r} fill="none" stroke="var(--muted)" strokeWidth="3" />
            <circle
              cx="12"
              cy="12"
              r={r}
              fill="none"
              stroke="var(--kb)"
              strokeWidth="3"
              strokeDasharray={`${dash} ${c}`}
              strokeLinecap="round"
              transform="rotate(-90 12 12)"
            />
          </svg>
          {pct}%
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-2">
        <ul className="flex flex-col gap-0.5">
          {rows.map((row) => (
            <li key={row.key}>
              <button
                type="button"
                disabled={row.n === 0 || !onFocusSegment}
                onClick={() => row.idx !== null && onFocusSegment?.(row.idx)}
                className="flex w-full items-center justify-between rounded px-1.5 py-1 text-xs hover:bg-muted disabled:opacity-50"
              >
                <span className={row.tone}>{row.label}</span>
                <span className="tabular-nums">{row.n} 句</span>
              </button>
            </li>
          ))}
        </ul>
        {counts.warnings.length > 0 ? (
          <ul className="mt-1 border-t border-border/60 pt-1">
            {counts.warnings.slice(0, 4).map((w, i) => (
              <li key={i} className="px-1.5 py-0.5 text-[11px] leading-relaxed text-warn">
                {w}
              </li>
            ))}
          </ul>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

export default TrustSummary;
