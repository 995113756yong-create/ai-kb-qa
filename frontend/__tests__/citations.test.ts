import { describe, expect, it } from "vitest";

import { collectCitations, sourceByCitation } from "@/lib/citations";
import type { Source } from "@/lib/types";

const mkSource = (index: number, source: string, snippet: string): Source => ({
  index,
  doc_id: `doc${index}`,
  source,
  page: null,
  snippet,
  content: snippet,
});

const SOURCES: Source[] = [mkSource(1, "a.txt", "A 的内容"), mkSource(2, "b.txt", "B 的内容")];

// 全链路用引用编号 n（从 1 开始），禁止用数组下标。
// 回归点：旧实现用 sources[index] 取证据，差了一位——
// 点 [1] 取到第 2 条，只有一条证据时取到 undefined。

describe("sourceByCitation", () => {
  it("按编号取到正确的条目（不是数组下标）", () => {
    expect(sourceByCitation(SOURCES, 1)?.source).toBe("a.txt");
    expect(sourceByCitation(SOURCES, 2)?.source).toBe("b.txt");
  });

  it("编号超出范围返回 undefined", () => {
    expect(sourceByCitation(SOURCES, 3)).toBeUndefined();
  });

  it("null / undefined 输入返回 undefined", () => {
    expect(sourceByCitation(null, 1)).toBeUndefined();
    expect(sourceByCitation(undefined, 1)).toBeUndefined();
  });

  it("只有一条证据时，点 [1] 仍能取到（旧实现在这里返回 undefined）", () => {
    const one: Source[] = [mkSource(1, "only.txt", "唯一")];
    expect(sourceByCitation(one, 1)?.source).toBe("only.txt");
  });

  it("编号非连续时按 index 匹配，不依赖位置", () => {
    const sparse: Source[] = [mkSource(2, "second.txt", "2"), mkSource(5, "fifth.txt", "5")];
    expect(sourceByCitation(sparse, 5)?.source).toBe("fifth.txt");
    expect(sourceByCitation(sparse, 1)).toBeUndefined();
  });
});

describe("collectCitations", () => {
  it("识别 [1] 形式并按出现顺序去重", () => {
    expect(collectCitations("甲 [1]，乙 [2]，丙 [1]").map((t) => t.index)).toEqual([1, 2]);
  });

  it("兼容流式阶段残留的 [E1] 形式", () => {
    expect(collectCitations("甲 [E1]，乙 [E2]").map((t) => t.index)).toEqual([1, 2]);
  });
});
