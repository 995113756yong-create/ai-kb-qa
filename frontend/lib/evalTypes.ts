// eval-summary.json 的类型定义（由后端 scripts/eval.py --json 导出）。
// 与 docs/ui-revamp-plan.md 第 9 节的 schema 一致。

export type EvalModeStat = {
  total: number;
  passed: number;
  avg_latency_ms: number;
  avg_tokens: number;
};

export type EvalCategoryStat = {
  passed: number;
  total: number;
};

export type EvalFailure = {
  case_id: string;
  mode: "strict" | "reference";
  category: string;
  question: string;
  expected: string;
  answer: string;
  reason: string;
};

export type EvalSummary = {
  commit: string;
  generated_at: string;
  modes: {
    strict: EvalModeStat;
    reference: EvalModeStat;
  };
  categories: Record<string, EvalCategoryStat>;
  failures: EvalFailure[];
};
