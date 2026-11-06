import { describe, expect, it } from "vitest";

import { splitByRanges, type Range } from "@/lib/highlight";

// 片段的 [start, end) 区间可能重叠（切分时有 overlap）。
// splitByRanges 把它们切成互不重叠的小段，且拼接结果必须等于原文。

describe("splitByRanges", () => {
  it("区间不重叠时，切出的段拼起来等于原文", () => {
    const text = "0123456789";
    const ranges: Range[] = [
      { start: 0, end: 3, n: 1, active: true },
      { start: 5, end: 8, n: 2, active: false },
    ];

    const slices = splitByRanges(text, ranges);
    expect(slices.map((s) => s.text).join("")).toBe(text);
  });

  it("只标记被区间覆盖的部分", () => {
    const text = "abcdefghij";
    const ranges: Range[] = [{ start: 2, end: 5, n: 1, active: true }];

    const slices = splitByRanges(text, ranges);
    const highlighted = slices.filter((s) => s.ns.length > 0);
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0].text).toBe("cde");
    expect(highlighted[0].active).toBe(true);
    expect(highlighted[0].ns).toEqual([1]);
  });

  it("区间重叠时，当前证据优先，且拼接仍等于原文", () => {
    const text = "0123456789";
    const ranges: Range[] = [
      { start: 0, end: 6, n: 1, active: false },
      { start: 4, end: 9, n: 2, active: true },
    ];

    const slices = splitByRanges(text, ranges);
    expect(slices.map((s) => s.text).join("")).toBe(text);

    // 重叠区 [4,6) 应归为 active
    const overlap = slices.find((s) => s.text.startsWith("45"));
    expect(overlap).toBeDefined();
    expect(overlap!.active).toBe(true);
    // 重叠区同时属于 1 和 2
    expect(overlap!.ns).toEqual([1, 2]);
  });

  it("区间越界时安全截断，不抛异常", () => {
    const text = "abc";
    const ranges: Range[] = [
      { start: 1, end: 999, n: 1, active: true },
      { start: -5, end: 2, n: 2, active: false },
    ];

    const slices = splitByRanges(text, ranges);
    expect(slices.map((s) => s.text).join("")).toBe(text);
  });

  it("完全越界的区间被丢弃", () => {
    const text = "abc";
    const slices = splitByRanges(text, [{ start: 10, end: 20, n: 1, active: true }]);
    expect(slices).toEqual([{ text: "abc", ns: [], active: false }]);
  });

  it("空区间列表返回整段普通文本", () => {
    expect(splitByRanges("hello", [])).toEqual([{ text: "hello", ns: [], active: false }]);
  });

  it("空文本返回空数组", () => {
    expect(splitByRanges("", [{ start: 0, end: 1, n: 1, active: true }])).toEqual([]);
  });

  it("相邻且归属相同的段会被合并", () => {
    const text = "0123456789";
    const ranges: Range[] = [
      { start: 0, end: 3, n: 1, active: true },
      { start: 3, end: 6, n: 1, active: true },
    ];

    const slices = splitByRanges(text, ranges);
    const active = slices.filter((s) => s.active);
    expect(active).toHaveLength(1);
    expect(active[0].text).toBe("012345");
  });

  it("多段高亮时每个编号都记在 ns 里", () => {
    const text = "abcdef";
    const ranges: Range[] = [
      { start: 0, end: 6, n: 1, active: true },
      { start: 0, end: 6, n: 2, active: false },
    ];
    const slices = splitByRanges(text, ranges);
    expect(slices).toHaveLength(1);
    expect(slices[0].ns).toEqual([1, 2]);
    expect(slices[0].active).toBe(true);
  });
});
