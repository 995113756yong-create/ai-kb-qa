"use client";

import type { MouseEvent } from "react";

import { useCitationFocus } from "@/lib/citationFocus";
import { sourceByCitation } from "@/lib/citations";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { Segment as TraceSegment, Source } from "@/lib/types";

type Props = {
  text: string;
  onJump?: (index: number) => void;
  /** 消息 id：给句子加 id/data-cites，供阅读器「被引用于」定位（M5.2） */
  messageId?: string;
  /** 证据列表：悬停引用时预览片段 */
  sources?: Source[] | null;
  /** 点击引用：打开阅读器 */
  onOpenEvidence?: (n: number) => void;
  /** 句子级溯源数据：有值时按句渲染并标注来源底色 */
  segments?: TraceSegment[] | null;
};

// 把 [1]、[2] 这类引用渲染成可点击的标签，其余内容一律按纯文本渲染。
// 不用 Markdown 渲染库，也不允许 dangerouslySetInnerHTML。
const CITATION_RE = /\[(\d+)\]/g;

type Segment = { kind: "text"; text: string } | { kind: "citation"; index: number };

function splitSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(CITATION_RE)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      segments.push({ kind: "text", text: text.slice(cursor, start) });
    }
    segments.push({ kind: "citation", index: Number(match[1]) });
    cursor = start + match[0].length;
  }

  if (cursor < text.length) {
    segments.push({ kind: "text", text: text.slice(cursor) });
  }
  return segments;
}

// 引用编号：悬停预览片段，点击打开阅读器。
// 触屏设备不显示悬停卡（matchMedia("(hover: none)")），点击直接打开。
function CitationChip({
  n,
  source,
  onOpen,
}: {
  n: number;
  source?: Source;
  onOpen: (e: MouseEvent<HTMLElement>) => void;
}) {
  const { activeN } = useCitationFocus();
  const isLinked = activeN === n;

  const button = (
    <button
      type="button"
      data-testid={`citation-${n}`}
      data-linked={isLinked ? "true" : undefined}
      onClick={(e) => onOpen(e)}
      className={
        "mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/10 px-1 text-[10px] font-semibold text-primary transition-colors hover:bg-primary/20 " +
        (isLinked ? "ring-2 ring-primary/40" : "")
      }
      aria-label={`查看证据 ${n}${source?.source ? `：${source.source}` : ""}`}
    >
      {n}
    </button>
  );

  if (!source) return button;

  return (
    <HoverCard openDelay={200} closeDelay={120}>
      <HoverCardTrigger asChild>{button}</HoverCardTrigger>
      <HoverCardContent className="w-80">
        <p className="text-[11px] text-muted-foreground">
          {source.source ?? "未知文档"}
          {source.page !== null && source.page !== undefined ? ` · 第 ${source.page} 页` : ""}
        </p>
        <p className="mt-1 line-clamp-4 text-[13px] leading-[1.6]">
          {source.snippet.length > 120 ? `${source.snippet.slice(0, 120)}…` : source.snippet}
        </p>
        <p className="mt-2 text-[11px] text-primary">点击查看原文 →</p>
      </HoverCardContent>
    </HoverCard>
  );
}

function SegmentBody({
  segment,
  onJump,
  messageId,
  index,
}: {
  segment: TraceSegment;
  onJump?: (index: number) => void;
  messageId?: string;
  index?: number;
}) {
  // 每段内部仍复用引用渲染逻辑，编号照常可点击
  const hasWarning = segment.warnings.length > 0;
  const isGeneral = segment.kind === "general";
  const style = hasWarning
    ? "underline decoration-wavy decoration-warn decoration-2 underline-offset-4"
    : isGeneral
      ? "bg-general-bg underline decoration-dotted decoration-general decoration-1 underline-offset-4"
      : "";
  const title = hasWarning
    ? segment.warnings.join("\n")
    : isGeneral
      ? "一般知识，非知识库内容"
      : undefined;

  const cites = (segment.citations ?? []).join(",");
  return (
    <span
      data-kind={segment.kind}
      data-warn={hasWarning ? "true" : undefined}
      data-cites={cites || undefined}
      id={messageId && index !== undefined ? `${messageId}-seg-${index}` : undefined}
      className={style}
      title={title}
    >
      <AnswerView text={segment.text} onJump={onJump} />
    </span>
  );
}

export default function AnswerView({ text, onJump, segments, messageId, sources, onOpenEvidence }: Props) {
  function handleClick(event: MouseEvent<HTMLElement>, index: number) {
    event.preventDefault();
    if (onOpenEvidence) onOpenEvidence(index);
    else onJump?.(index);
  }

  if (segments && segments.length > 0) {
    return (
      <div className="whitespace-pre-wrap text-[13.5px] leading-7 text-foreground">
        {segments.map((segment, i) => (
          <SegmentBody key={i} segment={segment} onJump={onJump} messageId={messageId} index={i} />
        ))}
      </div>
    );
  }

  return (
    <div className="whitespace-pre-wrap text-[13.5px] leading-7 text-foreground">
      {splitSegments(text).map((segment, i) =>
        segment.kind === "text" ? (
          <span key={i}>{segment.text}</span>
        ) : (
          <CitationChip
            key={i}
            n={segment.index}
            source={sourceByCitation(sources, segment.index)}
            onOpen={(e) => handleClick(e, segment.index)}
          />
        ),
      )}
    </div>
  );
}
