"use client";

// 专家切换器：当前专家大按钮 + 下拉菜单（全部专家 / 专家广场 / 新建专家）。
// 删除放在条目悬停菜单，default 不显示；AlertDialog 二次确认。

import { useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import ExpertGallery from "@/components/workspace/ExpertGallery";
import CreateExpertWizard from "@/components/workspace/CreateExpertWizard";
import { cn } from "@/lib/utils";
import type { AgentInfo } from "@/lib/types";
import type { AgentCreateRequest } from "@/lib/types";

export type ExpertSwitcherProps = {
  agents: AgentInfo[];
  activeAgentId: string;
  activeAgent: AgentInfo | undefined;
  onSwitch: (agentId: string) => void;
  onDelete: (agentId: string) => void;
  galleryOpen: boolean;
  onGalleryOpenChange: (open: boolean) => void;
  wizardOpen: boolean;
  onWizardOpenChange: (open: boolean) => void;
  /** 新建专家回调（透传给 CreateExpertWizard 的 onCreate） */
  onCreateAgent: (req: AgentCreateRequest) => void;
};

export default function ExpertSwitcher({
  agents,
  activeAgentId,
  activeAgent,
  onSwitch,
  onDelete,
  galleryOpen,
  onGalleryOpenChange,
  wizardOpen,
  onWizardOpenChange,
  onCreateAgent,
}: ExpertSwitcherProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<AgentInfo | null>(null);

  const emoji = activeAgent?.emoji ?? "🤖";
  const name = activeAgent?.name ?? "加载中…";
  const docCount = activeAgent?.doc_count;

  return (
    <div data-testid="agent-list">
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            data-testid="expert-switcher"
            className="flex w-full items-center gap-2.5 rounded-lg border bg-card p-2.5 text-left transition-colors hover:bg-muted/60"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-primary/20 to-primary/5 text-base">
              {emoji}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{name}</span>
              <span className="block text-[11px] text-muted-foreground">
                {docCount !== undefined ? `${docCount} 份文档` : "专家"}
              </span>
            </span>
            <span className="text-muted-foreground">⌄</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          {agents.map((agent) => (
            <DropdownMenuItem
              key={agent.agent_id}
              data-testid={`agent-item-${agent.agent_id}`}
              onSelect={() => onSwitch(agent.agent_id)}
              className="group flex items-center justify-between gap-2"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span>{agent.emoji}</span>
                <span className="truncate">{agent.name}</span>
                {agent.agent_id === activeAgentId ? (
                  <span className="ml-auto size-1.5 rounded-full bg-primary" />
                ) : null}
              </span>
              {agent.agent_id !== "default" ? (
                <button
                  type="button"
                  aria-label={`删除专家 ${agent.name}`}
                  className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmDelete(agent);
                  }}
                >
                  ✕
                </button>
              ) : null}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => onGalleryOpenChange(true)}>
            🏛 专家广场…
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onWizardOpenChange(true)}>
            ＋ 新建专家…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirmDelete !== null} onOpenChange={(open) => !open && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除专家「{confirmDelete?.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后该专家的文档、索引和会话记录都会清除，无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmDelete) onDelete(confirmDelete.agent_id);
                setConfirmDelete(null);
              }}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {galleryOpen ? (
        <ExpertGallery open={galleryOpen} onOpenChange={onGalleryOpenChange} agents={agents} onSwitch={onSwitch} />
      ) : null}
      {wizardOpen ? (
        <CreateExpertWizard open={wizardOpen} onOpenChange={onWizardOpenChange} agents={agents} onCreate={onCreateAgent} />
      ) : null}
    </div>
  );
}
