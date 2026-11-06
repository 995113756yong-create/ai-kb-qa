import { describe, expect, it } from "vitest";

import { en } from "@/lib/i18n/en";
import { zh } from "@/lib/i18n/zh";
import {
  DEFAULT_LOCALE,
  LOCALES,
  diffKeys,
  interpolate,
  messages,
  resolve,
} from "@/lib/i18n/messages";

// 字典层：中英必须完全对齐，占位符也要一致。
// 这是「漏翻译在编译/测试阶段暴露」的保障。

describe("i18n 字典", () => {
  it("中英键集合完全一致", () => {
    expect(diffKeys(zh, en)).toEqual([]);
  });

  it("没有空字符串文案", () => {
    const empties: string[] = [];
    const walk = (obj: object, prefix = "") => {
      for (const [k, v] of Object.entries(obj)) {
        if (typeof v === "string") {
          if (!v.trim()) empties.push(`${prefix}${k}`);
        } else if (typeof v === "object" && v !== null) {
          walk(v, `${prefix}${k}.`);
        }
      }
    };
    walk(zh);
    walk(en);
    expect(empties).toEqual([]);
  });

  it("两侧占位符集合一致", () => {
    const placeholders = (s: string) =>
      (s.match(/\{(\w+)\}/g) ?? []).sort().join(",");

    const walk = (a: object, b: object, prefix = "") => {
      const bad: string[] = [];
      for (const [k, va] of Object.entries(a)) {
        const vb = (b as Record<string, unknown>)[k];
        if (typeof va === "string" && typeof vb === "string") {
          if (placeholders(va) !== placeholders(vb)) {
            bad.push(`${prefix}${k}: zh[${placeholders(va)}] vs en[${placeholders(vb)}]`);
          }
        } else if (typeof va === "object" && va !== null) {
          bad.push(...walk(va, vb as object, `${prefix}${k}.`));
        }
      }
      return bad;
    };
    expect(walk(zh, en)).toEqual([]);
  });

  it("默认语言是中文", () => {
    expect(DEFAULT_LOCALE).toBe("zh");
    expect(LOCALES).toContain("zh");
    expect(LOCALES).toContain("en");
  });
});

describe("resolve", () => {
  it("按点号路径取值", () => {
    expect(resolve(messages.zh, "chat.send")).toBe("发送");
    expect(resolve(messages.en, "chat.send")).toBe("Send");
  });

  it("取不到时原样返回 key（不返回 undefined）", () => {
    expect(resolve(messages.zh, "nope.nothing")).toBe("nope.nothing");
  });

  it("路径中途是字符串时不抛异常", () => {
    expect(resolve(messages.zh, "chat.send.deeper")).toBe("chat.send.deeper");
  });
});

describe("interpolate", () => {
  it("替换占位符", () => {
    expect(interpolate("证据 {n} / {total}", { n: 1, total: 3 })).toBe("证据 1 / 3");
  });

  it("缺参时保留占位符，便于发现漏传", () => {
    expect(interpolate("证据 {n} / {total}", { n: 1 })).toBe("证据 1 / {total}");
  });

  it("没有变量时原样返回", () => {
    expect(interpolate("纯文本")).toBe("纯文本");
  });

  it("变量值为 0 时也能替换", () => {
    expect(interpolate("{n} 份文档", { n: 0 })).toBe("0 份文档");
  });
});