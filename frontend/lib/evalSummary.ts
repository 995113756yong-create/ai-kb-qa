import type { EvalSummary } from "@/lib/evalTypes";

// 评测看板的数据访问层：读取构建期生成的 eval-summary.json，
// 展示层只依赖这里的类型与取数函数。

export type { EvalSummary } from "@/lib/evalTypes";

export function passRate(passed: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((passed / total) * 1000) / 10;
}

export function avgLatencyMs(summary: EvalSummary): number {
  return summary.modes.strict.avg_latency_ms;
}

/** 严格模式平均分（0-100），保留一位小数。 */
export function strictScore(summary: EvalSummary): number {
  return passRate(summary.modes.strict.passed, summary.modes.strict.total);
}

/** 参考模式平均分（0-100），保留一位小数。 */
export function referenceScore(summary: EvalSummary): number {
  return passRate(summary.modes.reference.passed, summary.modes.reference.total);
}

/** 各分类通过率，按通过率升序（最弱的排前面）。 */
export function categoryRates(summary: EvalSummary): Array<{ category: string; rate: number }> {
  const rows = Object.entries(summary.categories).map(([category, stat]) => ({
    category,
    rate: passRate(stat.passed, stat.total),
  }));
  return rows.sort((a, b) => a.rate - b.rate);
}

/** 未通过用例（strict 模式），按分类分组。 */
export function failedCases(summary: EvalSummary): EvalSummary["failures"] {
  return summary.failures.filter((f) => f.mode === "strict");
}
