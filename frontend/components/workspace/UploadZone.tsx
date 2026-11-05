"use client";

// 上传区：拖拽 + 点击选择。上传中显示进度态，失败通过 toast 提示。

import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

export type UploadZoneProps = {
  /** 上传模式：upload 直接调 API；local 仅选文件回调（向导里创建专家后再上传） */
  mode?: "upload" | "local";
  uploading?: boolean;
  onUpload?: (file: File) => void;
  /** local 模式：选中的文件列表变化时回调（含顺序） */
  files?: File[];
  onFilesChange?: (files: File[]) => void;
  /** 支持多选（local 模式向导默认多选） */
  multiple?: boolean;
  compact?: boolean;
  className?: string;
};

export function UploadZone({
  mode = "upload",
  uploading = false,
  onUpload,
  files = [],
  onFilesChange,
  multiple = false,
  compact = false,
  className,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const isLocal = mode === "local";

  const pick = () => inputRef.current?.click();

  const handleFiles = (list: FileList | undefined) => {
    if (!list || list.length === 0) return;
    if (isLocal) {
      const incoming = Array.from(list);
      onFilesChange?.(multiple ? [...files, ...incoming] : [incoming[0]]);
    } else {
      const file = list[0];
      if (file) onUpload?.(file);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const removeLocal = (idx: number) => {
    if (onFilesChange) onFilesChange(files.filter((_, i) => i !== idx));
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        data-testid="upload-zone"
        role="button"
        tabIndex={0}
        onClick={pick}
        onKeyDown={(e) => e.key === "Enter" && pick()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-border text-center text-muted-foreground transition-colors hover:border-primary/50 hover:bg-primary/5",
          compact ? "px-3 py-4 text-xs" : "px-4 py-8 text-sm",
          dragging && "border-primary bg-primary/10",
          !isLocal && uploading && "pointer-events-none opacity-60",
        )}
      >
        <span className="text-lg">{!isLocal && uploading ? "⏳" : "📄"}</span>
        <span>{!isLocal && uploading ? "上传中…" : "点击或拖拽上传文档"}</span>
        {!compact && <span className="text-xs text-muted-foreground/70">支持 PDF / Markdown / TXT</span>}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.md,.markdown,.txt"
          multiple={isLocal && multiple}
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files ?? undefined);
            e.target.value = "";
          }}
        />
      </div>
      {isLocal && files.length > 0 ? (
        <ul data-testid="upload-zone-files" className="flex flex-col gap-1">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center justify-between rounded-md border border-border/60 bg-muted/40 px-2 py-1 text-xs">
              <span className="truncate">{f.name}</span>
              <button
                type="button"
                aria-label={`移除 ${f.name}`}
                className="ml-2 shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  removeLocal(i);
                }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
