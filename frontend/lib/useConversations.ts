"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ChatMessage, Conversation } from "@/lib/chat";
import { clearConversations, loadConversations, saveConversations } from "@/lib/store";

// 会话管理：按专家隔离的多会话，IndexedDB 持久化（不可用时内存态降级）。

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useConversations(agentId: string, initialConversationId: string | null = null) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  // loadedFor 记录「当前 conversations 属于哪个专家」：
  // 切换专家后到加载完成之前两者不相等，此时不落盘，避免把上个专家的会话写进新 key。
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const agentRef = useRef(agentId);

  // agentRef 只在 effect 里写（渲染期不能改 ref），供 create / save 使用最新 expert。
  useEffect(() => {
    agentRef.current = agentId;
  }, [agentId]);

  // 切换专家：清空当前视图并加载新专家的会话。
  // 所有 setState 都在 await 之后，避免 effect 同步阶段触发级联渲染。
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const list = await loadConversations(agentId);
      if (cancelled) return;
      setConversations(list);
      // 优先恢复链接里指定的会话（?c=<id>），找不到时退回最近一条
      const wanted = initialConversationId && list.some((c) => c.id === initialConversationId)
        ? initialConversationId
        : (list.length > 0 ? list[0].id : null);
      setCurrentId(wanted);
      setLoaded(true);
      setLoadedFor(agentId);
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId, initialConversationId]);

  // 会话变化时自动保存（防抖 400ms）。只在「已加载且属于当前专家」时写。
  useEffect(() => {
    if (!loaded || loadedFor !== agentId) return;
    const timer = setTimeout(() => {
      void saveConversations(agentId, conversations);
    }, 400);
    return () => clearTimeout(timer);
  }, [conversations, loaded, loadedFor, agentId]);

  const current = conversations.find((c) => c.id === currentId) ?? null;

  const create = useCallback((title = "新会话"): string => {
    const conv: Conversation = {
      id: newId(),
      agentId: agentRef.current,
      title,
      messages: [],
      updatedAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setCurrentId(conv.id);
    return conv.id;
  }, []);

  const remove = useCallback((id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      setCurrentId((cur) => (cur === id ? (next.length > 0 ? next[0].id : null) : cur));
      return next;
    });
  }, []);

  const rename = useCallback((id: string, title: string) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  }, []);

  const appendMessages = useCallback((id: string, messages: ChatMessage[]) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, messages: [...c.messages, ...messages], updatedAt: Date.now() } : c,
      ),
    );
  }, []);

  const updateMessage = useCallback((id: string, messageId: string, updater: (m: ChatMessage) => ChatMessage) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              updatedAt: Date.now(),
              messages: c.messages.map((m) => (m.id === messageId ? updater(m) : m)),
            }
          : c,
      ),
    );
  }, []);

  /** 用同一条消息位置替换（重新生成场景） */
  const replaceMessage = useCallback((id: string, messageId: string, message: ChatMessage) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              updatedAt: Date.now(),
              messages: c.messages.map((m) => (m.id === messageId ? message : m)),
            }
          : c,
      ),
    );
  }, []);

  /** 首条用户消息自动把「新会话」命名为问题摘要 */
  const ensureTitle = useCallback((id: string, question: string) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== id || c.messages.length > 0 || c.title !== "新会话") return c;
        const title = question.length > 18 ? question.slice(0, 18) + "…" : question;
        return { ...c, title };
      }),
    );
  }, []);

  const clearAll = useCallback(() => {
    void clearConversations(agentRef.current);
    setConversations([]);
    setCurrentId(null);
  }, []);

  return {
    conversations,
    current,
    currentId,
    loaded,
    setCurrentId,
    create,
    remove,
    rename,
    appendMessages,
    updateMessage,
    replaceMessage,
    ensureTitle,
    clearAll,
  };
}
