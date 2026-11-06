"use client";

import Link from "next/link";

import { useAgents } from "@/hooks/useAgents";
import type { AgentInfo } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

// 专家画廊：独立页面版，网格展示全部专家并支持跳转到对话。
// 与聊天工作台里的 ExpertGallery（Dialog 版）共用同一份 /api/agents 数据。

const GRADIENTS = [
  "from-sky-500 to-indigo-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-violet-500 to-purple-500",
  "from-cyan-500 to-blue-500",
];

function gradientFor(agentId: string): string {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) hash = (hash * 31 + agentId.charCodeAt(i)) | 0;
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  const { t } = useI18n();
  return (
    <Link
      href={`/?agent=${encodeURIComponent(agent.agent_id)}`}
      data-testid={`gallery-agent-${agent.agent_id}`}
      className="flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card transition-shadow hover:shadow-md"
    >
      <div className={`h-12 bg-gradient-to-r ${gradientFor(agent.agent_id)}`} />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">{agent.emoji || "🤖"}</span>
          <span className="font-medium">{agent.name}</span>
          {agent.builtin ? (
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {t("experts.builtin")}
            </span>
          ) : null}
        </div>
        {agent.description ? (
          <p className="line-clamp-3 text-xs text-muted-foreground">{agent.description}</p>
        ) : (
          <p className="text-xs text-muted-foreground">{t("experts.noDescription")}</p>
        )}
        <span className="mt-auto pt-2 text-[11px] text-muted-foreground">
          {t("experts.answerModeLabel", { mode: agent.answer_mode === "strict" ? t("experts.strictRef") : t("experts.reference") })}
        </span>
      </div>
    </Link>
  );
}

export default function ExpertsPage() {
  const { t } = useI18n();
  const { agents, loading, error } = useAgents();

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("experts.galleryTitle")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("experts.gallerySubtitle")}
          </p>
        </div>
        <nav className="flex gap-2 text-sm">
          <Link
            href="/"
            className="rounded-lg border border-border/60 px-3 py-1.5 transition-colors hover:bg-muted"
          >
            {t("experts.backToChat")}
          </Link>
          <Link
            href="/eval"
            className="rounded-lg border border-border/60 px-3 py-1.5 transition-colors hover:bg-muted"
          >
            {t("eval.title")}
          </Link>
        </nav>
      </header>

      {loading ? (
        <p className="mt-10 text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : error ? (
        <p className="mt-10 text-sm text-destructive">{error}</p>
      ) : agents.length === 0 ? (
        <p className="mt-10 text-sm text-muted-foreground">{t("experts.empty")}</p>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <AgentCard key={a.agent_id} agent={a} />
          ))}
        </div>
      )}
    </main>
  );
}
