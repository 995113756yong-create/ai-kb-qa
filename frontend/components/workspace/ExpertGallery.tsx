"use client";

// 专家广场：大尺寸 Dialog，卡片网格展示全部专家，底部「＋ 新建专家」虚线卡。
// 封面渐变按 agent_id 哈希从 6 组预设中选，同一专家颜色稳定。

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { AgentInfo } from "@/lib/types";

const GRADIENTS = [
  "from-sky-500 to-indigo-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-violet-500 to-purple-500",
  "from-cyan-500 to-blue-500",
];

function gradientFor(agentId: string): string {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) hash = (hash * 31 + agentId.charCodeAt(i)) | 0;
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

export type ExpertGalleryProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agents: AgentInfo[];
  onSwitch: (agentId: string) => void;
  onCreate?: () => void;
};

export default function ExpertGallery({ open, onOpenChange, agents, onSwitch, onCreate }: ExpertGalleryProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>专家广场</DialogTitle>
        </DialogHeader>
        <div className="grid max-h-[70vh] gap-4 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <div
              key={agent.agent_id}
              data-testid={`gallery-agent-${agent.agent_id}`}
              className="flex flex-col overflow-hidden rounded-xl border bg-card transition-shadow hover:shadow-md"
            >
              <div className={`h-12 bg-gradient-to-r ${gradientFor(agent.agent_id)}`} />
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{agent.emoji}</span>
                  <span className="truncate text-sm font-semibold">{agent.name}</span>
                </div>
                <p className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground">
                  {agent.description || "暂无简介"}
                </p>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="rounded-full bg-muted px-2 py-0.5">
                    {agent.answer_mode === "strict" ? "严格模式" : "参考模式"}
                  </span>
                  <span className="text-muted-foreground">{agent.doc_count ?? 0} 份文档</span>
                </div>
                <button
                  type="button"
                  className="mt-auto rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-primary hover:text-primary-foreground"
                  onClick={() => {
                    onSwitch(agent.agent_id);
                    onOpenChange(false);
                  }}
                >
                  开始对话
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            data-testid="gallery-create-card"
            onClick={() => {
              onOpenChange(false);
              onCreate?.();
            }}
            className="flex min-h-44 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
          >
            <span className="text-2xl">＋</span>
            <span>新建专家</span>
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
