// 字典类型：以 zh 为基准，en 必须完全对齐（缺键或多键都会编译报错）。
// 这就是「零依赖 + 类型安全」的来源——漏翻译在 tsc 阶段就会失败。

import { en } from "./en";
import { zh } from "./zh";

export type Messages = typeof zh;

/** 把字典的叶子键展开成点号路径，例如 "chat.send"。 */
type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string
    ? P extends ""
      ? K
      : `${P}.${K}`
    : Leaves<T[K], P extends "" ? K : `${P}.${K}`>;
}[keyof T & string];

export type MessageKey = Leaves<Messages>;

export type Locale = "zh" | "en";

export const LOCALES: readonly Locale[] = ["zh", "en"] as const;
export const DEFAULT_LOCALE: Locale = "zh";
export const LOCALE_STORAGE_KEY = "ai-kb-qa.locale";

export const messages: Record<Locale, Messages> = {
  zh,
  // 断言到 Messages：键缺失或多键都会在这里报错
  en: en as unknown as Messages,
};

/** 检查 en 与 zh 的键集合是否完全一致（用于单测）。 */
export function diffKeys(a: object, b: object, prefix = ""): string[] {
  const out: string[] = [];
  const ka = Object.keys(a).sort();
  const kb = Object.keys(b).sort();

  for (const k of ka) {
    if (!kb.includes(k)) {
      out.push(`missing in other: ${prefix}${k}`);
      continue;
    }
    const va = (a as Record<string, unknown>)[k];
    const vb = (b as Record<string, unknown>)[k];
    const isObjA = typeof va === "object" && va !== null;
    const isObjB = typeof vb === "object" && vb !== null;
    if (isObjA && isObjB) {
      out.push(...diffKeys(va as object, vb as object, `${prefix}${k}.`));
    } else if (isObjA !== isObjB) {
      out.push(`shape mismatch: ${prefix}${k}`);
    }
  }
  for (const k of kb) {
    if (!ka.includes(k)) out.push(`extra in other: ${prefix}${k}`);
  }
  return out;
}

/** 取点号路径上的字符串。取不到时原样返回 key，避免界面出现空白。 */
export function resolve(dict: Messages, key: string): string {
  const parts = key.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (typeof cur !== "object" || cur === null) return key;
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === "string" ? cur : key;
}

/** 把 {name} 占位符替换成实参。缺参时保留占位符，便于发现漏传。 */
export function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (m, name: string) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m,
  );
}