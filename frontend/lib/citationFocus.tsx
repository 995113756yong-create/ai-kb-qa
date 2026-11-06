"use client";

// 句子与证据的双向联动：按消息维护「当前悬停/激活的引用编号」。
// 由 MessageList 为每条 assistant 消息提供一个 Provider。

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type CitationFocusValue = {
  /** 当前激活的引用编号 n（从 1 开始），null 表示无 */
  activeN: number | null;
  setActiveN: (n: number | null) => void;
};

const CitationFocusContext = createContext<CitationFocusValue>({
  activeN: null,
  setActiveN: () => {},
});

export function CitationFocusProvider({ children }: { children: ReactNode }) {
  const [activeN, setActiveN] = useState<number | null>(null);
  const value = useMemo(() => ({ activeN, setActiveN }), [activeN]);
  return <CitationFocusContext.Provider value={value}>{children}</CitationFocusContext.Provider>;
}

export function useCitationFocus(): CitationFocusValue {
  return useContext(CitationFocusContext);
}
