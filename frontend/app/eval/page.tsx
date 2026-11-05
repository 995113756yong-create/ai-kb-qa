import Link from "next/link";

import {
  categoryRates,
  failedCases,
  modeRows,
  modeStat,
  pct,
} from "@/lib/evalSummary";
import type { EvalSummary } from "@/lib/evalTypes";
import summaryJson from "@/data/eval-summary.json";

// 评测看板：静态读取构建期的 eval-summary.json，无需运行时接口。
// 用于回答「当前检索质量如何、哪类问题最弱、哪些用例没过」。

const summary = summaryJson as unknown as EvalSummary;

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export default function EvalPage() {
  const strict = modeStat(summary, "strict");
  const rows = modeRows(summary);
  const cats = categoryRates(summary, "strict");
  const failed = failedCases(summary, "strict");

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{summary.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            生成于 {summary.generated_at} · commit{" "}
            <span className="font-mono text-xs">{summary.commit}</span>
          </p>
        </div>
        <nav className="flex gap-2 text-sm">
          <Link
            href="/"
            className="rounded-lg border border-border/60 px-3 py-1.5 transition-colors hover:bg-muted"
          >
            返回对话
          </Link>
          <Link
            href="/experts"
            className="rounded-lg border border-border/60 px-3 py-1.5 transition-colors hover:bg-muted"
          >
            专家画廊
          </Link>
        </nav>
      </header>

      <section className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="严格模式通过率" value={pct(strict.pass_rate)} hint={`${strict.total} 个用例`} />
        <StatCard label="检索命中率" value={pct(strict.retrieval_rate)} />
        <StatCard label="引用率" value={pct(strict.citation_rate)} />
        <StatCard label="P95 延迟" value={`${strict.latency_p95} ms`} hint={`P50 ${strict.latency_p50} ms`} />
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium">两种回答模式对比</h2>
        <div className="mt-3 overflow-hidden rounded-xl border border-border/60">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">指标</th>
                <th className="px-4 py-2 text-right font-medium">strict</th>
                <th className="px-4 py-2 text-right font-medium">reference</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label} className="border-t border-border/40">
                  <td className="px-4 py-2 text-muted-foreground">{r.label}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.strict}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium">分类通过率（由弱到强）</h2>
        <ul className="mt-3 space-y-2">
          {cats.map((c) => (
            <li key={c.category} className="flex items-center gap-3">
              <span className="w-28 shrink-0 font-mono text-xs">{c.category}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(2, c.rate * 100)}%` }}
                />
              </div>
              <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                {pct(c.rate)}
              </span>
              <span className="w-10 shrink-0 text-right text-[11px] text-muted-foreground">
                n={c.n}
              </span>
            </li>
          ))}
          {cats.length === 0 ? (
            <li className="text-sm text-muted-foreground">暂无分类数据</li>
          ) : null}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium">未通过用例（strict，{failed.length} 条）</h2>
        {failed.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">全部通过。</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {failed.slice(0, 20).map((c) => (
              <li key={c.id} className="rounded-xl border border-border/60 bg-card p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-mono">{c.id}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5">{c.category}</span>
                  <span>{c.grounded ? "已溯源" : "未溯源"}</span>
                </div>
                <p className="mt-2 text-sm font-medium">{c.question}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  问题：{c.problems.join("；")}
                </p>
                <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">{c.answer}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
