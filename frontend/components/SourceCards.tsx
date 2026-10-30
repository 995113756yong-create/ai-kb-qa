"use client";

import { useState } from "react";

import type { Source } from "@/lib/types";

type Props = {
  sources: Source[];
};

export default function SourceCards({ sources }: Props) {
  const [open, setOpen] = useState(true);

  if (sources.length === 0) {
    return null;
  }

  return (
    <section className="mt-3 border-t border-dashed border-zinc-200 pt-2.5 dark:border-zinc-800">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 transition-colors hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
      >
        <span aria-hidden>📎</span>
        出处（{sources.length}）{open ? "收起" : "展开"}
      </button>

      {open && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {sources.map((source) => (
            <li
              key={source.index}
              id={`source-${source.index}`}
              data-testid={`source-card-${source.index}`}
              className="rounded-lg border border-zinc-100 bg-zinc-50/80 p-2.5 text-xs leading-relaxed transition-colors hover:border-indigo-200 dark:border-zinc-800 dark:bg-zinc-800/60 dark:hover:border-indigo-800"
            >
              <p className="flex items-center gap-1.5 font-semibold text-zinc-700 dark:text-zinc-200">
                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-100 px-1 text-[10px] font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                  {source.index}
                </span>
                [{source.index}] {source.source ?? "未知文档"}
                {source.page ? ` · 第${source.page}页` : ""}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-zinc-500 dark:text-zinc-400">
                {source.snippet}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function useSourceMap(sources: Source[]): Map<number, Source> {
  return new Map(sources.map((source) => [source.index, source]));
}
