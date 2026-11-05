"use client";

import { useCallback, useEffect, useState } from "react";

import { listAgents } from "@/lib/api";
import type { AgentInfo } from "@/lib/types";

// 专家列表加载：与后端 /api/agents 对接，失败静默为空数组。
// 刷新函数供「创建专家后刷新」使用。

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
    void refresh();
  }, [refresh]);

  return { agents, loading, error, refresh };
}
