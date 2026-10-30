"use client";

import { useState } from "react";

import type { Step } from "@/lib/chat";

type Props = {
  steps: Step[];
  running: boolean;
  elapsedMs: number | null;
  defaultOpen: boolean;
};

function toolIcon(name: string): string {
  if (name === "search_kb") {
    return "🔍";
  }
  if (name === "read_chunk") {
    return "📄";
  }
  if (name === "list_documents") {
    return "🗂";
  }
  return "🛠";
}

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args).filter(([, v]) => v !== undefined && v !== null);
  if (entries.length === 0) {
    return "";
  }
  return entries
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

export default function AgentTrace({ steps, running, elapsedMs, defaultOpen }: Props) {
  // 生成过程中默认展开，完成后折叠成一行摘要
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const open = manualOpen ?? (running ? true : defaultOpen);

  const searchCount = steps.filter((s) => s.kind === "tool_call" && s.name === "search_kb").length;
  const summary =
    elapsedMs === null
      ? `检索 ${searchCount} 次，进行中…`
      : `检索 ${searchCount} 次，用时 ${(elapsedMs / 1000).toFixed(1)}s`;

  return (
    <section className="mb-2.5 overflow-hidden rounded-xl border border-zinc-200/80 bg-zinc-50/80 dark:border-zinc-800/80 dark:bg-zinc-900/50">
      <button
        type="button"
        onClick={() => setManualOpen(!open)}
        aria-expanded={open}
        data-testid="trace-toggle"
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs text-zinc-600 transition-colors hover:bg-zinc-100/70 dark:text-zinc-400 dark:hover:bg-zinc-800/50"
      >
        {running ? (
          <span className="flex h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500">
            <span className="h-full w-full animate-ping rounded-full bg-indigo-400" />
          </span>
        ) : (
          <span aria-hidden className="shrink-0 text-[11px]">⚡</span>
        )}
        <span className="font-medium text-zinc-700 dark:text-zinc-300">Agent 过程</span>
        <span className="text-zinc-400">{summary}</span>
        <span className="ml-auto text-zinc-400">{open ? "收起 ▲" : "展开 ▼"}</span>
      </button>

      {open && (
        <ol className="flex flex-col gap-1 border-t border-zinc-200/60 px-2.5 py-2 dark:border-zinc-800/60" data-testid="trace-steps">
          {steps.map((step) => {
            if (step.kind === "decompose") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-indigo-600 dark:text-indigo-300">
                  🧩 问题拆解为 {step.queries.length} 个子问题：{step.queries.join("；")}
                </li>
              );
            }
            if (step.kind === "thought") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                  💭 {step.text}
                </li>
              );
            }
            if (step.kind === "tool_call") {
              return (
                <li key={step.key} className="text-xs text-zinc-700 dark:text-zinc-300">
                  {toolIcon(step.name)} {step.name}({formatArgs(step.args)})
                </li>
              );
            }
            return (
              <li
                key={step.key}
                className={`pl-5 text-xs leading-relaxed ${
                  step.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
                }`}
              >
                {step.ok ? "→" : "✕"} {step.summary}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
