"use client";

// 会话列表侧栏卡片：＋新会话、按日期分组、重命名/删除、当前高亮。

import { useState } from "react";

import { groupConversations, conversationTitle } from "@/lib/conversations";
import { cn } from "@/lib/utils";
import type { Conversation } from "@/lib/chat";

export type ConversationListProps = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  className?: string;
};

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
  className,
}: ConversationListProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const groups = groupConversations(conversations);

  // 进入重命名时用会话标题作初值。用「上一次的 renamingId」判断是否刚进入，
  // 避免 effect 里无条件 setState（react-hooks/set-state-in-effect）。
  const [prevRenamingId, setPrevRenamingId] = useState<string | null>(null);
  if (renamingId !== prevRenamingId) {
    setPrevRenamingId(renamingId);
    if (renamingId !== null) {
      const c = conversations.find((x) => x.id === renamingId);
      if (c) setDraft(conversationTitle(c));
    }
  }

  const commitRename = () => {
    if (renamingId !== null) {
      const title = draft.trim();
      if (title) onRename(renamingId, title);
    }
    setRenamingId(null);
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <button
        type="button"
        data-testid="new-conversation"
        onClick={onNew}
        className="flex items-center justify-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors hover:border-primary/50 hover:bg-primary/5"
      >
        ＋ 新会话
      </button>

      {conversations.length === 0 && (
        <p className="px-1 py-4 text-center text-xs text-muted-foreground">还没有会话</p>
      )}

      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-1">
          <p className="px-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
            {group.label}
          </p>
          {group.items.map((c) => {
            const active = c.id === activeId;
            if (renamingId === c.id) {
              return (
                <input
                  key={c.id}
                  data-testid={`rename-input-${c.id}`}
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename();
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  className="rounded-md border border-primary/50 bg-background px-2 py-1.5 text-sm outline-none"
                />
              );
            }
            return (
              <div
                key={c.id}
                data-testid={`conversation-${c.id}`}
                onClick={() => onSelect(c.id)}
                className={cn(
                  "group flex cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted",
                )}
              >
                <span className="truncate">{conversationTitle(c)}</span>
                <span className="hidden shrink-0 gap-1 group-hover:flex">
                  <button
                    type="button"
                    aria-label="重命名"
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenamingId(c.id);
                    }}
                    className="rounded p-0.5 text-xs hover:bg-background"
                  >
                    ✏️
                  </button>
                  <button
                    type="button"
                    aria-label="删除"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c.id);
                    }}
                    className="rounded p-0.5 text-xs hover:bg-background"
                  >
                    🗑️
                  </button>
                </span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
