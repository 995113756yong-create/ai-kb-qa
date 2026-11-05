"use client";

import { useEffect } from "react";

// 全局快捷键：⌘K / Ctrl+K 打开命令面板，⌘B / Ctrl+B 折叠侧栏，Esc 关闭。
// 匹配单个键时不监听输入框内的按键（Escape 除外）。

export type HotkeyHandlers = {
  onOpenPalette?: () => void;
  onToggleSidebar?: () => void;
  onEscape?: () => void;
};

export function useHotkeys(handlers: HotkeyHandlers): void {
  useEffect(() => {
    const onKeydown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (e.key.toLowerCase() === "k" && mod) {
        e.preventDefault();
        handlers.onOpenPalette?.();
        return;
      }
      if (e.key.toLowerCase() === "b" && mod) {
        e.preventDefault();
        handlers.onToggleSidebar?.();
        return;
      }
      if (e.key === "Escape") {
        handlers.onEscape?.();
      }
    };
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, [handlers]);
}
