"use client";

import { useCallback, useEffect, useState } from "react";

import { listDocs, uploadDoc, deleteDoc } from "@/lib/api";
import type { DocInfo } from "@/lib/types";

// 知识库文档列表：上传后自动刷新，删除由父组件调用 API 后手动刷新。

export type UseDocsResult = {
  docs: DocInfo[];
  loading: boolean;
  uploading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  upload: (file: File) => Promise<DocInfo | null>;
  remove: (docId: string) => Promise<boolean>;
};

export function useDocs(agentId?: string): UseDocsResult {
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await listDocs(agentId);
      setDocs(res.docs ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载文档列表失败");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  const upload = useCallback(
    async (file: File): Promise<DocInfo | null> => {
      setUploading(true);
      try {
        const res = await uploadDoc(file, agentId);
        await refresh();
        setError(null);
        // UploadResponse 无 doc 字段；按响应字段拼一条最小 DocInfo 供调用方提示
        return {
          doc_id: res.doc_id,
          filename: res.filename,
          ext: res.filename.split(".").pop() ?? "",
          size: res.size,
          chunks: res.chunks,
          uploaded_at: new Date().toISOString(),
        };
      } catch (e) {
        setError(e instanceof Error ? e.message : "上传失败");
        return null;
      } finally {
        setUploading(false);
      }
    },
    [agentId, refresh],
  );

  const remove = useCallback(
    async (docId: string): Promise<boolean> => {
      try {
        await deleteDoc(docId, agentId);
        await refresh();
        setError(null);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "删除失败");
        return false;
      }
    },
    [agentId, refresh],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { docs, loading, uploading, error, refresh, upload, remove };
}
