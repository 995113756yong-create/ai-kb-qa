// eval-summary.json 的类型定义（由后端 scripts/eval.py --json 导出）。
// 字段与 docs/ui-revamp-plan.md 第 9 节一致，并以实际产物为准。

export type EvalCaseSource = {
  index: number;
  source: string;
  content: string;
};

export type EvalCase = {
  id: string;
  question: string;
  category: string;
  mode: "strict" | "reference";
  answer: string;
  problems: string[];
  grounded: boolean;
  steps: number;
  sources: EvalCaseSource[];
};

export type EvalCategoryStat = {
  n: number;
  pass_rate: number;
};

export type EvalModeStat = {
  total: number;
  errors: number;
  retrieval_rate: number;
  answer_rate: number;
  citation_rate: number;
  reject_rate: number;
  pass_rate: number;
  avg_ratio: number;
  numeric_consistency: number | null;
  faithfulness: number | null;
  latency_p50: number;
  latency_p95: number;
  avg_tokens: number;
  price_in: number;
  price_out: number;
  by_category: Record<string, EvalCategoryStat>;
  cases: EvalCase[];
};

export type EvalSummary = {
  generated_at: string;
  title: string;
  commit: string;
  source: string;
  modes: {
    strict: EvalModeStat;
    reference: EvalModeStat;
  };
};
