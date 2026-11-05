// localStorage 的薄封装：SSR 与测试环境（无 window）下静默降级。
// 值统一按 JSON 字符串存储，读写失败一律返回 null 不抛错。

export function lsGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function lsSet(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 隐私模式或存储超限时忽略
  }
}

export function lsRemove(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function lsGetJson<T>(key: string): T | null {
  const raw = lsGet(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function lsSetJson<T>(key: string, value: T): void {
  try {
    lsSet(key, JSON.stringify(value));
  } catch {
    // 循环引用等情况忽略
  }
}
