import type { Conversation } from "@/lib/chat";

// 会话列表的纯函数集合：按日期分组、排序、标题推导。
// 与 useConversations 解耦，方便单测。

const DAY_MS = 86_400_000;

export type ConversationGroup = {
  label: string;
  items: Conversation[];
};

function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function formatDayLabel(ts: number): string {
  const today = startOfDay(Date.now());
  const day = startOfDay(ts);
  const diff = Math.round((today - day) / DAY_MS);
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff < 7) return "本周";
  if (diff < 30) return "本月";
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** 按更新时间倒序分组，组内也按更新时间倒序。 */
export function groupConversations(list: Conversation[]): ConversationGroup[] {
  const sorted = [...list].sort((a, b) => b.updatedAt - a.updatedAt);
  const groups: ConversationGroup[] = [];
  for (const c of sorted) {
    const label = formatDayLabel(c.updatedAt);
    const last = groups[groups.length - 1];
    if (last && last.label === label) {
      last.items.push(c);
    } else {
      groups.push({ label, items: [c] });
    }
  }
  return groups;
}

/** 会话标题：第一条用户消息截断 20 字，否则「新会话」。 */
export function conversationTitle(c: Conversation): string {
  const firstUser = c.messages.find((m) => m.role === "user");
  if (!firstUser) return "新会话";
  const text = firstUser.text.trim();
  if (!text) return "新会话";
  return text.length > 20 ? `${text.slice(0, 20)}…` : text;
}
