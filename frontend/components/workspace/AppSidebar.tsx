"use client";

// 左栏：专家切换 + 会话列表 + 知识库面板（方案 6.2）。
// 从上到下三块，各块职责拆给 ExpertSwitcher / ConversationList / KnowledgePanel。

import { useState } from "react";

import { ConversationList } from "@/components/workspace/ConversationList";
import { KnowledgePanel } from "@/components/workspace/KnowledgePanel";
import ExpertSwitcher from "@/components/workspace/ExpertSwitcher";
import type { AgentInfo, AgentCreateRequest, DocInfo } from "@/lib/types";
import type { Conversation } from "@/lib/chat";

export type AppSidebarProps = {
  agents: AgentInfo[];
  agentsLoading?: boolean;
  activeAgentId: string;
  onSwitchAgent: (agentId: string) => void;
  conversations: Conversation[];
  currentId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  docs: DocInfo[];
  docsLoading?: boolean;
  onUpload: (file: File) => void;
  onDeleteDoc: (docId: string) => void;
  onCreateAgent: (payload: AgentCreateRequest) => void;
  onDeleteAgent: (agentId: string) => void;
  activeAgent: AgentInfo | undefined;
};

export default function AppSidebar(props: AppSidebarProps) {
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto bg-sidebar p-3">
      <ExpertSwitcher
        agents={props.agents}
        activeAgentId={props.activeAgentId}
        activeAgent={props.activeAgent}
        onSwitch={props.onSwitchAgent}
        onDelete={props.onDeleteAgent}
        galleryOpen={galleryOpen}
        onGalleryOpenChange={setGalleryOpen}
        wizardOpen={wizardOpen}
        onWizardOpenChange={setWizardOpen}
        onCreateAgent={props.onCreateAgent}
      />
      <ConversationList
        conversations={props.conversations}
        activeId={props.currentId}
        onSelect={props.onSelectConversation}
        onNew={props.onNewChat}
        onDelete={props.onDeleteConversation}
        onRename={props.onRenameConversation}
      />
      <KnowledgePanel
        docs={props.docs}
        uploading={props.docsLoading ?? false}
        onUpload={props.onUpload}
        onDelete={props.onDeleteDoc}
      />
    </div>
  );
}
