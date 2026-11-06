"use client";

import type { MouseEvent } from "react";

import type { Segment as TraceSegment } from "@/lib/types";

type Props = {
  text: string;
  onJump?: (index: number) => void;
  /** 消息 id：给句子加 id/data-cites，供阅读器「被引用于」定位（M5.2） */
  messageId?: string;
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

export default function AnswerView({ text, onJump, segments, messageId }: Props) {
  function handleClick(event: MouseEvent<HTMLButtonElement>, index: number) {
    event.preventDefault();
    onJump?.(index);
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
          <button
            key={i}
            type="button"
            onClick={(event) => handleClick(event, segment.index)}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/10 px-1 text-[10px] font-semibold text-primary transition-colors hover:bg-primary/20"
            aria-label={`查看证据 ${segment.index}`}
          >
            {segment.index}
          </button>
        ),
      )}
    </div>
  );
}
