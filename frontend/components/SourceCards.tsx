"use client";

import { useMemo, useState } from "react";

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
    <section className="mt-3 border-t border-dashed border-zinc-300 pt-2 dark:border-zinc-700">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-xs font-medium text-blue-600 hover:underline"
      >
        出处（{sources.length}）{open ? "收起" : "展开"}
      </button>

      {open && (
        <ul className="mt-2 flex flex-col gap-2">
          {sources.map((source) => (
            <li
              key={source.index}
              id={`source-${source.index}`}
              data-testid={`source-card-${source.index}`}
              className="rounded-md bg-zinc-50 p-2 text-xs leading-relaxed dark:bg-zinc-800"
            >
              <p className="font-semibold text-zinc-700 dark:text-zinc-200">
                [{source.index}] {source.source ?? "未知文档"}
                {source.page ? ` · 第${source.page}页` : ""}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-zinc-600 dark:text-zinc-400">
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
  return useMemo(
    () => new Map(sources.map((source) => [source.index, source])),
    [sources],
  );
}
