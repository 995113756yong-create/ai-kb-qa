import type { Conversation } from "@/lib/chat";

// 会话本地持久化：localStorage（按专家隔离）。
// 不用 IndexedDB：线上已有 localStorage 里的历史会话，换存储会丢用户数据；
// 且 jsdom 无 indexedDB，会让组件测试拿不到落盘结果。

const KEY_PREFIX = "kbqa:conversations:";

function storage(): Storage | null {
  try {
    if (typeof localStorage === "undefined") {
      return null;
    }
    return localStorage;
  } catch {
    return null;
  }
}

export async function loadConversations(agentId: string): Promise<Conversation[]> {
  const s = storage();
  if (!s) return [];
  try {
    const raw = s.getItem(KEY_PREFIX + agentId);
    if (!raw) return [];
    const list = JSON.parse(raw) as unknown;
    if (!Array.isArray(list)) return [];
    return list as Conversation[];
  } catch {
    return [];
  }
}

export async function saveConversations(agentId: string, list: Conversation[]): Promise<void> {
  const s = storage();
  if (!s) return;
  try {
    s.setItem(KEY_PREFIX + agentId, JSON.stringify(list));
  } catch {
    // 存储失败（超额/隐私模式）不影响主流程
  }
}

export async function clearConversations(agentId: string): Promise<void> {
  const s = storage();
  if (!s) return;
  try {
    s.removeItem(KEY_PREFIX + agentId);
  } catch {
    // 忽略
  }
}
