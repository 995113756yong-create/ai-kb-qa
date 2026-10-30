"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, deleteDoc, uploadDoc } from "@/lib/api";
import type { DocInfo } from "@/lib/types";

const ACCEPT = [".txt", ".md", ".pdf"];
const MAX_MB = 10;

type Props = {
  docs: DocInfo[];
  loading: boolean;
  onRefresh: () => Promise<void>;
};

const EXT_ICON: Record<string, string> = {
  ".pdf": "📕",
  ".md": "📝",
  ".txt": "📄",
};

function formatSize(size: number): string {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)}MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)}KB`;
  }
  return `${size}B`;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function DocSidebar({ docs, loading, onRefresh }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) {
        return;
      }
      setError(null);

      // 先在前端拦掉明显不合法的文件，省一次无谓的往返
      const dot = file.name.lastIndexOf(".");
      const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
      if (!ACCEPT.includes(ext)) {
        setError(`只支持 ${ACCEPT.join(" / ")} 格式`);
        return;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setError(`文件不能超过 ${MAX_MB}MB`);
        return;
      }

      setUploading(true);
      try {
        await uploadDoc(file);
        await onRefresh();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "上传失败，请重试");
      } finally {
        setUploading(false);
        if (inputRef.current) {
          // 清空以便重复选择同一个文件
          inputRef.current.value = "";
        }
      }
    },
    [onRefresh],
  );

  const handleDelete = useCallback(
    async (doc: DocInfo) => {
      if (!window.confirm(`确定删除《${doc.filename}》？删除后无法恢复。`)) {
        return;
      }
      setError(null);
      try {
        await deleteDoc(doc.doc_id);
        await onRefresh();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "删除失败，请重试");
      }
    },
    [onRefresh],
  );

  return (
    <aside className="flex h-full flex-col gap-3 border-r border-zinc-200/80 bg-white p-4 dark:border-zinc-800/80 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
          文档
          <span className="ml-1 text-xs font-normal text-zinc-400">{docs.length}</span>
        </h2>
        <button
          type="button"
          onClick={handlePick}
          disabled={uploading}
          className="brand-gradient rounded-lg px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:shadow-md active:scale-95 disabled:opacity-50"
        >
          {uploading ? "上传中…" : "+ 上传"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT.join(",")}
          aria-label="选择要上传的文档"
          data-testid="file-input"
          className="hidden"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="thin-scroll flex-1 overflow-y-auto">
        {loading && <p className="text-xs text-zinc-400">加载中…</p>}

        {!loading && docs.length === 0 && (
          <div className="rounded-xl border border-dashed border-zinc-200 p-4 text-center text-xs leading-relaxed text-zinc-400 dark:border-zinc-700">
            <div className="mb-1 text-2xl">📂</div>
            还没有文档。
            <br />
            先上传 TXT / MD / PDF，再开始提问。
          </div>
        )}

        <ul className="flex flex-col gap-1.5">
          {docs.map((doc) => (
            <li
              key={doc.doc_id}
              className="group flex items-start gap-2 rounded-xl border border-transparent bg-zinc-50/80 px-2.5 py-2 text-xs transition-colors hover:border-zinc-200 hover:bg-white dark:bg-zinc-900/60 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
            >
              <span className="mt-0.5 shrink-0 text-sm" aria-hidden>
                {EXT_ICON[doc.ext] ?? "📄"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-zinc-800 dark:text-zinc-100" title={doc.filename}>
                  {doc.filename}
                </p>
                <p className="mt-0.5 text-[11px] text-zinc-400">
                  {doc.chunks} 片段 · {formatSize(doc.size)} · {formatTime(doc.uploaded_at)}
                </p>
              </div>
              <button
                type="button"
                aria-label={`删除 ${doc.filename}`}
                onClick={() => void handleDelete(doc)}
                className="shrink-0 rounded px-1 text-zinc-400 opacity-0 transition-opacity hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
              >
                删除
              </button>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[11px] leading-relaxed text-zinc-400">
        支持 {ACCEPT.join(" / ")}，单文件不超过 {MAX_MB}MB
      </p>
    </aside>
  );
}
