"use client";

// 知识库面板：标题「知识库 · N」可折叠，内含 UploadZone 与文档列表。

import { useState } from "react";

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
import { UploadZone } from "@/components/workspace/UploadZone";
import { cn } from "@/lib/utils";
import { formatBytes } from "@/lib/numbers";
import { timeAgo } from "@/lib/numbers";
import type { DocInfo } from "@/lib/types";

export type KnowledgePanelProps = {
  docs: DocInfo[];
  uploading: boolean;
  onUpload: (file: File) => void;
  onDelete: (docId: string) => void;
  className?: string;
};

const FILE_STYLE: Record<string, { icon: string; color: string }> = {
  pdf: { icon: "📕", color: "text-rose-500" },
  md: { icon: "📘", color: "text-blue-500" },
  txt: { icon: "📄", color: "text-muted-foreground" },
};

function fileStyle(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return FILE_STYLE[ext] ?? { icon: "📄", color: "text-muted-foreground" };
}

export function KnowledgePanel({
  docs,
  uploading,
  onUpload,
  onDelete,
  className,
}: KnowledgePanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocInfo | null>(null);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <button
        type="button"
        data-testid="knowledge-panel-toggle"
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center justify-between px-1 text-sm font-medium text-foreground"
      >
        <span>知识库 · {docs.length}</span>
        <span className="text-xs text-muted-foreground">{collapsed ? "▸" : "▾"}</span>
      </button>

      {!collapsed && (
        <div className="flex flex-col gap-2">
          <UploadZone uploading={uploading} onUpload={onUpload} compact />
          <div className="flex max-h-64 flex-col gap-1 overflow-y-auto">
            {docs.map((doc) => {
              const style = fileStyle(doc.filename);
              return (
                <div
                  key={doc.doc_id}
                  data-testid={`doc-${doc.doc_id}`}
                  className="group flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-muted"
                >
                  <span className={cn("shrink-0", style.color)}>{style.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-foreground" title={doc.filename}>
                      {doc.filename}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {doc.chunks ?? 0} 片 · {formatBytes(doc.size ?? 0)} · {timeAgo(new Date(doc.uploaded_at ?? Date.now()).getTime())}
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label={`删除 ${doc.filename}`}
                    onClick={() => setPendingDelete(doc)}
                    className="hidden shrink-0 rounded p-1 text-xs hover:bg-background group-hover:block"
                  >
                    🗑️
                  </button>
                </div>
              );
            })}
            {docs.length === 0 && (
              <p className="px-2 py-3 text-center text-xs text-muted-foreground">
                还没有文档，上传一份试试
              </p>
            )}
          </div>
        </div>
      )}

      <AlertDialog open={pendingDelete !== null}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除文档？</AlertDialogTitle>
            <AlertDialogDescription>
              确认删除「{pendingDelete?.filename}」？删除后基于该文档的回答将失去证据来源。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingDelete(null)}>取消</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-doc"
              onClick={() => {
                if (pendingDelete) onDelete(pendingDelete.doc_id);
                setPendingDelete(null);
              }}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
