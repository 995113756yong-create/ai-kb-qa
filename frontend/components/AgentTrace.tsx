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

const INTENT_LABELS: Record<string, string> = {
  chat: "闲聊，直接回复",
  list_docs: "查看文档清单",
  kb_query: "需要查知识库，先预检索",
  uncertain: "交给模型判断",
};

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
  // 折叠态要把改写结果露出来，让用户一眼看出系统有没有理解错
  const rewriteStep = steps.find((s) => s.kind === "rewrite");

  const summary =
    elapsedMs === null
      ? `检索 ${searchCount} 次，进行中…`
      : `检索 ${searchCount} 次，用时 ${(elapsedMs / 1000).toFixed(1)}s`;

  return (
    <section className="mb-2.5 overflow-hidden rounded-xl border border-border bg-muted/40">
      <button
        type="button"
        onClick={() => setManualOpen(!open)}
        aria-expanded={open}
        data-testid="trace-toggle"
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-muted"
      >
        {running ? (
          <span className="flex h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500">
            <span className="h-full w-full animate-ping rounded-full bg-indigo-400" />
          </span>
        ) : (
          <span aria-hidden className="shrink-0 text-[11px]">⚡</span>
        )}
        <span className="font-medium text-foreground">Agent 过程</span>
        <span className="text-muted-foreground">{summary}</span>
        {rewriteStep && !open ? (
          <span className="ml-auto truncate pl-2 text-sky-600 dark:text-sky-400" data-testid="trace-rewritten">
            理解为：{rewriteStep.rewritten.length > 24
              ? `${rewriteStep.rewritten.slice(0, 24)}…`
              : rewriteStep.rewritten}
          </span>
        ) : null}
        <span className={`${rewriteStep && !open ? "" : "ml-auto"} shrink-0 pl-2 text-muted-foreground`}>
          {open ? "收起 ▲" : "展开 ▼"}
        </span>
      </button>

      {open && (
        <ol className="flex flex-col gap-1 border-t border-border px-2.5 py-2" data-testid="trace-steps">
          {steps.map((step) => {
            if (step.kind === "intent") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-general">
                  🧭 意图识别：{INTENT_LABELS[step.intent] ?? step.intent}（{step.reason}）
                </li>
              );
            }
            if (step.kind === "rewrite") {
              return (
                <li
                  key={step.key}
                  className="text-xs leading-relaxed text-sky-600 dark:text-sky-300"
                  title={`原话：${step.original}`}
                >
                  理解为：{step.rewritten}
                </li>
              );
            }
            if (step.kind === "decompose") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-primary">
                  🧩 问题拆解为 {step.queries.length} 个子问题：{step.queries.join("；")}
                </li>
              );
            }
            if (step.kind === "thought") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-zinc-600 dark:text-muted-foreground">
                  💭 {step.text}
                </li>
              );
            }
            if (step.kind === "tool_call") {
              return (
                <li key={step.key} className="text-xs text-foreground">
                  {toolIcon(step.name)} {step.name}({formatArgs(step.args)})
                </li>
              );
            }
            return (
              <li
                key={step.key}
                className={`pl-5 text-xs leading-relaxed ${
                  step.ok ? "text-kb" : "text-destructive"
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
