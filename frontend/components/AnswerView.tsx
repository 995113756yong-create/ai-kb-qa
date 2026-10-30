"use client";

import type { MouseEvent } from "react";

type Props = {
  text: string;
  onJump?: (index: number) => void;
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

export default function AnswerView({ text, onJump }: Props) {
  function handleClick(event: MouseEvent<HTMLButtonElement>, index: number) {
    event.preventDefault();
    onJump?.(index);
  }

  return (
    <div className="whitespace-pre-wrap text-[13.5px] leading-7 text-zinc-800 dark:text-zinc-100">
      {splitSegments(text).map((segment, i) =>
        segment.kind === "text" ? (
          <span key={i}>{segment.text}</span>
        ) : (
          <button
            key={i}
            type="button"
            onClick={(event) => handleClick(event, segment.index)}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-100 px-1 text-[10px] font-semibold text-indigo-700 transition-colors hover:bg-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-300 dark:hover:bg-indigo-500/30"
            aria-label={`查看出处 ${segment.index}`}
          >
            {segment.index}
          </button>
        ),
      )}
    </div>
  );
}
