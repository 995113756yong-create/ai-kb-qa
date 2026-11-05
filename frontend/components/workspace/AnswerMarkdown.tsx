"use client";

// 回答正文的 Markdown 渲染：[E1] 引用替换为可点击的 CitationChip。
// 数学公式与代码块语法高亮在方案中标注为可选，先保证正文结构正确。

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationChip } from "@/components/workspace/CitationChip";
import { cn } from "@/lib/utils";

export type AnswerMarkdownProps = {
  content: string;
  onCitationClick?: (index: number) => void;
  className?: string;
};

const INLINE_CITATION_RE = /\[E(\d+)\]/g;

/** 把文本切成「普通文本 / 引用编号」交替的片段。 */
function splitCitations(text: string): Array<string | number> {
  const parts: Array<string | number> = [];
  let last = 0;
  for (const m of text.matchAll(INLINE_CITATION_RE)) {
    const start = m.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    parts.push(Number(m[1]));
    last = start + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function renderWithCitations(
  text: string,
  onCitationClick?: (index: number) => void,
): React.ReactNode[] {
  return splitCitations(text).map((part, i) =>
    typeof part === "number" ? (
      <CitationChip key={`c-${i}`} index={part} onClick={onCitationClick} />
    ) : (
      part
    ),
  );
}

export function AnswerMarkdown({ content, onCitationClick, className }: AnswerMarkdownProps) {
  return (
    <div
      data-testid="answer-markdown"
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none leading-relaxed",
        "[&_p]:my-2 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5",
        "[&_pre]:my-3 [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em]",
        "[&_h2]:mt-4 [&_h3]:mt-3 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{renderWithCitations(String(children ?? ""), onCitationClick)}</p>,
          li: ({ children }) => <li>{renderWithCitations(String(children ?? ""), onCitationClick)}</li>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
