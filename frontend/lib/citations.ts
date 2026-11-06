import type { Source } from "@/lib/types";

// 引用编号模型：把回答文本里的 [1] [2]（以及流式阶段可能残留的 [E1]）映射到 sources。
// 后端 finalize 会把编号重编为从 1 连续递增，Source.index 也是从 1 开始。
//
// 约定：**全链路传递引用编号 n（从 1 开始）**，取证据一律用 sourceByCitation，
// 禁止用数组下标 —— 两者差 1，直接用下标会取错条目（只有一条证据时取到 undefined）。

export type CitationToken = {
  /** 原始编号数字，如 [1] → 1、[E3] → 3 */
  index: number;
};

// 同时接受 [1] 与 [E1]：正文最终是 [1]，但流式中断时可能残留 [E1]
export const CITATION_RE = /\[(?:E)?(\d+)\]/g;

/** 收集文本中出现的全部引用编号，按出现顺序去重。 */
export function collectCitations(text: string): CitationToken[] {
  const seen = new Set<number>();
  const tokens: CitationToken[] = [];
  for (const m of text.matchAll(CITATION_RE)) {
    const index = Number(m[1]);
    if (!Number.isFinite(index) || seen.has(index)) continue;
    seen.add(index);
    tokens.push({ index });
  }
  return tokens;
}

/**
 * 按引用编号（从 1 开始，对应正文里的 [n]）取 source。
 * 禁止用数组下标。
 */
export function sourceByCitation(
  sources: Source[] | null | undefined,
  n: number,
): Source | undefined {
  return (sources ?? []).find((s) => s.index === n);
}

/** 文本中的原始残留编号（流式中断时可能出现）是否可清理，见 lib/answer.ts。 */
export function hasRawCitation(text: string): boolean {
  CITATION_RE.lastIndex = 0;
  return CITATION_RE.test(text);
}

/** 兼容旧调用：按 token 取 source。 */
export function resolveSource(token: CitationToken, sources: Source[]): Source | null {
  return sourceByCitation(sources, token.index) ?? null;
}
