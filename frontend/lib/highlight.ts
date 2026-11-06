// 高亮区间的切分：把可能重叠的片段区间切成互不重叠的小段。
// 片段有 overlap 时区间会重叠，直接渲染会出现嵌套或错乱的 mark。

export type Range = {
  /** 片段在文本中的起点（含） */
  start: number;
  /** 终点（不含） */
  end: number;
  /** 引用编号 n；当前证据单独标记 active */
  n: number;
  active: boolean;
};

export type Slice = {
  text: string;
  /** 这段是否高亮；为空表示普通文本 */
  ns: number[];
  active: boolean;
};

/**
 * 把文本按区间切成互不重叠的片段。
 *
 * - 所有区间端点排序后切成小段，每段归属「覆盖它的区间集合」
 * - 当前证据优先：某段只要被 active 区间覆盖，就标 active
 * - 越界区间安全截断，不抛异常
 * - 输出的 text 拼起来必须等于原文（渲染不丢字）
 */
export function splitByRanges(text: string, ranges: Range[]): Slice[] {
  const len = text.length;
  const valid = ranges
    .map((r) => ({
      ...r,
      start: Math.max(0, Math.min(r.start, len)),
      end: Math.max(0, Math.min(r.end, len)),
    }))
    .filter((r) => r.end > r.start);

  if (valid.length === 0) {
    return text ? [{ text, ns: [], active: false }] : [];
  }

  // 端点集合
  const points = new Set<number>([0, len]);
  for (const r of valid) {
    points.add(r.start);
    points.add(r.end);
  }
  const sorted = Array.from(points).sort((a, b) => a - b);

  const out: Slice[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (b <= a) continue;

    const covering = valid.filter((r) => r.start <= a && r.end >= b);
    if (covering.length === 0) {
      out.push({ text: text.slice(a, b), ns: [], active: false });
    } else {
      const active = covering.some((r) => r.active);
      // 同一段被多个编号覆盖时，全部记下（渲染时可显示多个徽标）
      const ns = Array.from(new Set(covering.map((r) => r.n))).sort((x, y) => x - y);
      out.push({ text: text.slice(a, b), ns, active });
    }
  }

  // 合并相邻且归属相同的段，减少 DOM 节点
  const merged: Slice[] = [];
  for (const s of out) {
    const prev = merged[merged.length - 1];
    if (
      prev &&
      prev.active === s.active &&
      prev.ns.length === s.ns.length &&
      prev.ns.every((v, i) => v === s.ns[i])
    ) {
      prev.text += s.text;
    } else {
      merged.push({ ...s });
    }
  }
  return merged;
}

/** 从片段列表算出某个 n 在文本里的字符区间。 */
export function locateChunk(
  text: string,
  chunk: { start: number; end: number },
): { start: number; end: number } | null {
  const len = text.length;
  const start = Math.max(0, Math.min(chunk.start, len));
  const end = Math.max(0, Math.min(chunk.end, len));
  return end > start ? { start, end } : null;
}
