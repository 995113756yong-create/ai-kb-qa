import type { Source } from "@/lib/types";

// 引用编号模型：把回答文本里的 [E1] [E2] 映射到 sources 下标。
// 后端保证编号从 E1 开始且连续，这里只做防御性处理。

export type CitationToken = {
  /** 原始编号数字，如 [E3] → 3 */
  index: number;
  /** 在 sources 数组里的下标（E1 → 0），越界时为 null */
  sourceIndex: number | null;
};

export const CITATION_RE = /\[E(\d+)\]/g;

/** 收集文本中出现的全部引用编号，按出现顺序去重。 */
export function collectCitations(text: string): CitationToken[] {
  const seen = new Set<number>();
  const tokens: CitationToken[] = [];
  for (const m of text.matchAll(CITATION_RE)) {
    const index = Number(m[1]);
    if (!Number.isFinite(index) || seen.has(index)) continue;
    seen.add(index);
    tokens.push({
      index,
      sourceIndex: index >= 1 ? index - 1 : null,
    });
  }
  return tokens;
}

/** 判断 sourceIndex 是否有效（在 sources 范围内）。 */
export function resolveSource(
  token: CitationToken,
  sources: Source[],
): Source | null {
  if (token.sourceIndex === null) return null;
  return sources[token.sourceIndex] ?? null;
}

/** 文本中的原始残留编号（流式中断时可能出现）是否可清理，见 lib/answer.ts。 */
export function hasRawCitation(text: string): boolean {
  CITATION_RE.lastIndex = 0;
  return CITATION_RE.test(text);
}
