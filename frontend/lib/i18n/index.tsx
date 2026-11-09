"use client";

// 语言上下文：默认中文，选择存 localStorage，与主题同样处理水合。
// 水合前一律渲染默认语言，避免服务端/客户端不一致。

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_STORAGE_KEY,
  messages,
  resolve,
  interpolate,
  type Locale,
  type MessageKey,
} from "./messages";

type I18nValue = {
  locale: Locale;
  setLocale: (next: Locale) => void;
  /** 取文案，支持 {name} 占位符 */
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  /** 是否已完成水合（用于避免闪烁） */
  ready: boolean;
};

// 默认值必须与 Provider 行为一致（含占位符替换），
// 否则在没有 Provider 的测试/孤立渲染场景下会显示 "证据 {n} / {total}"。
const defaultT = (key: MessageKey, vars?: Record<string, string | number>) =>
  interpolate(resolve(messages[DEFAULT_LOCALE], key), vars);

const I18nContext = createContext<I18nValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  t: defaultT,
  ready: false,
});

function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (raw && (LOCALES as readonly string[]).includes(raw)) return raw as Locale;
  } catch {
    // localStorage 被禁用（隐私模式）时静默降级
  }
  return null;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // 惰性初始化：首次渲染就读 localStorage。
  // 服务端渲染时 readStoredLocale 返回 null，用默认语言；
  // 客户端首次渲染直接拿到用户选择，不会出现"先中文再变英文"的闪烁。
  const [locale, setLocaleState] = useState<Locale>(() => readStoredLocale() ?? DEFAULT_LOCALE);
  const ready = true;

  // 同步 <html lang>，便于屏幕阅读器与浏览器断词
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // 存不进去也不影响本次会话
    }
  }, []);

  const t = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) =>
      interpolate(resolve(messages[locale], key), vars),
    [locale],
  );

  const value = useMemo(
    () => ({ locale, setLocale, t, ready }),
    [locale, setLocale, t, ready],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}

/** 只要 t 时用这个，减少解构噪音。 */
export function useT() {
  return useI18n().t;
}