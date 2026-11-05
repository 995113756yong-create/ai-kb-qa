import { useCallback, useEffect, useState } from "react";

import { listAgents } from "@/lib/api";
import type { AgentInfo } from "@/lib/types";

// 专家列表加载：与后端 /api/agents 对接，失败时把错误文案交给调用方展示。
// 刷新函数供「创建专家后刷新」使用。
//
// 注意：effect 里只调用异步函数，所有 setState 都发生在 await 之后，
// 不会在 effect 的同步阶段触发级联渲染（react-hooks/set-state-in-effect）。

export type UseAgentsResult = {
  agents: AgentInfo[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

export function useAgents(): UseAgentsResult {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await listAgents();
      setAgents(res.agents ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载专家列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listAgents();
        if (cancelled) return;
        setAgents(res.agents ?? []);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "加载专家列表失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { agents, loading, error, refresh };
}