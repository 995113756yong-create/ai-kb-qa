import type { EvalCase, EvalModeStat, EvalSummary } from "@/lib/evalTypes";

// 评测看板的数据访问层：读取构建期生成的 eval-summary.json，
// 展示层只依赖这里的类型与派生函数。

export type {
  EvalCase,
  EvalCategoryStat,
  EvalModeStat,
  EvalSummary,
} from "@/lib/evalTypes";

/** 0-1 的比率转百分数，保留一位小数。 */
export function pct(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "—";
  return `${(ratio * 100).toFixed(1)}%`;
}

export function modeStat(summary: EvalSummary, mode: "strict" | "reference"): EvalModeStat {
  return summary.modes[mode];
}

/** 两种模式的对比行，直接喂给表格。 */
export function modeRows(
  summary: EvalSummary,
): Array<{ label: string; strict: string; reference: string }> {
  const s = summary.modes.strict;
  const r = summary.modes.reference;
  return [
    { label: "用例数", strict: String(s.total), reference: String(r.total) },
    { label: "通过率", strict: pct(s.pass_rate), reference: pct(r.pass_rate) },
    { label: "检索命中", strict: pct(s.retrieval_rate), reference: pct(r.retrieval_rate) },
    { label: "作答率", strict: pct(s.answer_rate), reference: pct(r.answer_rate) },
    { label: "引用率", strict: pct(s.citation_rate), reference: pct(r.citation_rate) },
    { label: "拒答率", strict: pct(s.reject_rate), reference: pct(r.reject_rate) },
    {
      label: "数字一致性",
      strict: pct(s.numeric_consistency),
      reference: pct(r.numeric_consistency),
    },
    { label: "P50 延迟", strict: `${s.latency_p50} ms`, reference: `${r.latency_p50} ms` },
    { label: "P95 延迟", strict: `${s.latency_p95} ms`, reference: `${r.latency_p95} ms` },
    { label: "平均 token", strict: String(s.avg_tokens), reference: String(r.avg_tokens) },
    { label: "错误数", strict: String(s.errors), reference: String(r.errors) },
  ];
}

/** 各分类通过率，按通过率升序（最弱的排前面）。 */
export function categoryRates(
  summary: EvalSummary,
  mode: "strict" | "reference" = "strict",
): Array<{ category: string; n: number; rate: number }> {
  const rows = Object.entries(summary.modes[mode].by_category).map(([category, stat]) => ({
    category,
    n: stat.n,
    rate: stat.pass_rate,
  }));
  return rows.sort((a, b) => a.rate - b.rate);
}

/** 未通过用例（problems 非空），strict 优先。 */
export function failedCases(
  summary: EvalSummary,
  mode: "strict" | "reference" = "strict",
): EvalCase[] {
  return summary.modes[mode].cases.filter((c) => c.problems.length > 0);
}
