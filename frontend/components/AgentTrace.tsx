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
    <section className="mb-2 rounded-md border border-zinc-200 bg-zinc-50/70 dark:border-zinc-800 dark:bg-zinc-900/60">
      <button
        type="button"
        onClick={() => setManualOpen(!open)}
        aria-expanded={open}
        data-testid="trace-toggle"
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs text-zinc-600 dark:text-zinc-400"
      >
        <span className="font-medium">Agent 过程</span>
        <span className="text-zinc-400">{summary}</span>
        <span className="ml-auto text-zinc-400">{open ? "收起" : "展开"}</span>
      </button>

      {open && (
        <ol className="flex flex-col gap-1 px-2 pb-2" data-testid="trace-steps">
          {steps.map((step) => {
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
                  step.ok ? "text-zinc-500" : "text-red-600"
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
