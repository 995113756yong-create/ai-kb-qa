"use client";

import { useEffect, useState } from "react";

import { getDocContent } from "@/lib/api";
import type { DocContent } from "@/lib/types";

// 文档原文按 agentId:docId 缓存：同一份文档在一个会话里只请求一次。
// 用模块级 Map 存 Promise，并发打开同一份文档也只发一个请求。

const cache = new Map<string, Promise<DocContent>>();

export function loadDocContent(agentId: string, docId: string): Promise<DocContent> {
  const key = `${agentId}:${docId}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const p = getDocContent(docId, agentId).catch((e) => {
    // 失败不缓存，允许重试
    cache.delete(key);
    throw e;
  });
  cache.set(key, p);
  return p;
}

/** 测试用：清空缓存。 */
export function clearDocContentCache(): void {
  cache.clear();
}

export type UseDocContentResult = {
  data: DocContent | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
};

export function useDocContent(agentId: string, docId: string | null | undefined): UseDocContentResult {
  const [data, setData] = useState<DocContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const d = await loadDocContent(agentId, docId);
        if (cancelled) return;
        setData(d);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "加载原文失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId, docId, attempt]);

  return { data, loading, error, retry: () => setAttempt((n) => n + 1) };
}
