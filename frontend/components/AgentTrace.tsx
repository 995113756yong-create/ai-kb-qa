"use client";

import { useState } from "react";

import type { Step } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/messages";

type TFunc = (key: MessageKey, vars?: Record<string, string | number>) => string;

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

// 意图标签依赖当前语言，不能在模块级求值（那时拿不到 t），
// 改成函数，在组件内调用。
function intentLabels(t: TFunc): Record<string, string> {
  return {
    chat: t("trace.intentChat"),
    list_docs: t("trace.intentListDocs"),
    kb_query: t("trace.intentKbQuery"),
    uncertain: t("trace.intentUncertain"),
  };
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
  const { t, locale } = useI18n();
  // 生成过程中默认展开，完成后折叠成一行摘要
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const open = manualOpen ?? (running ? true : defaultOpen);

  const searchCount = steps.filter((s) => s.kind === "tool_call" && s.name === "search_kb").length;
  // 折叠态要把改写结果露出来，让用户一眼看出系统有没有理解错
  const rewriteStep = steps.find((s) => s.kind === "rewrite");

  const summary =
    elapsedMs === null
      ? t("trace.retrievalRunning", { n: searchCount })
      : t("trace.retrievalDone", { n: searchCount, s: (elapsedMs / 1000).toFixed(1) });

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
        <span className="font-medium text-foreground">{t("trace.agentProcess")}</span>
        <span className="text-muted-foreground">{summary}</span>
        {rewriteStep && !open ? (
          <span className="ml-auto truncate pl-2 text-sky-600 dark:text-sky-400" data-testid="trace-rewritten">
            {t("chat.rewriteUnderstood", {
              q:
                rewriteStep.rewritten.length > 24
                  ? `${rewriteStep.rewritten.slice(0, 24)}…`
                  : rewriteStep.rewritten,
            })}
          </span>
        ) : null}
        <span className={`${rewriteStep && !open ? "" : "ml-auto"} shrink-0 pl-2 text-muted-foreground`}>
          {open ? t("evidence.collapseArrow") : t("evidence.expandArrow")}
        </span>
      </button>

      {open && (
        <ol className="flex flex-col gap-1 border-t border-border px-2.5 py-2" data-testid="trace-steps">
          {steps.map((step) => {
            if (step.kind === "intent") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-general">
                  🧭 {t("trace.intentRecognized", { intent: intentLabels(t)[step.intent] ?? step.intent, reason: step.reason })}
                </li>
              );
            }
            if (step.kind === "rewrite") {
              return (
                <li
                  key={step.key}
                  className="text-xs leading-relaxed text-sky-600 dark:text-sky-300"
                  title={t("trace.originalText", { q: step.original })}
                >
                  {t("chat.rewriteUnderstood", { q: step.rewritten })}
                </li>
              );
            }
            if (step.kind === "decompose") {
              return (
                <li key={step.key} className="text-xs leading-relaxed text-primary">
                  🧩 {t("trace.decomposed", { n: step.queries.length, list: step.queries.join(locale === "zh" ? "；" : "; ") })}
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
