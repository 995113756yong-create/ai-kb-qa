"use client";

import { useEffect, useState } from "react";

// 运行中的耗时计时器：runStartedAt 有值时每 100ms 走一次时间，
// runStartedAt 为 null 时冻结在当前值（保留最后一次运行的耗时展示）。

export function useElapsed(runStartedAt: number | null): number {
  const [now, setNow] = useState<number>(() => runStartedAt ?? Date.now());

  useEffect(() => {
    if (runStartedAt === null) return;
    // 不在这里同步 setNow：interval 第一次回调在 100ms 后就会刷新，
    // 同步补一次只为了让首帧准确，却会触发级联渲染（react-hooks/set-state-in-effect）。
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [runStartedAt]);

  return runStartedAt === null ? 0 : now - runStartedAt;
}
