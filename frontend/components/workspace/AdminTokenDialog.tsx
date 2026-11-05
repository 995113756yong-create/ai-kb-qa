"use client";

// 管理员令牌录入对话框：首次访问需要 admin 权限的接口时弹出。
// 令牌存 localStorage（key: kb-admin-token），不落 URL。

import { useEffect, useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { lsGet, lsSet } from "@/lib/storage";

export type AdminTokenDialogProps = {
  open: boolean;
  /** 用户保存令牌后回调（新令牌或 null 表示清除） */
  onSave: (token: string | null) => void;
  onCancel?: () => void;
};

export const ADMIN_TOKEN_KEY = "kb-admin-token";

export function AdminTokenDialog({ open, onSave, onCancel }: AdminTokenDialogProps) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (open) setValue(lsGet(ADMIN_TOKEN_KEY) ?? "");
  }, [open]);

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>需要管理员令牌</AlertDialogTitle>
          <AlertDialogDescription>
            创建专家、删除文档等管理操作需要管理员令牌。令牌只保存在本机浏览器，不会出现在链接里。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <input
          data-testid="admin-token-input"
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="粘贴管理员令牌"
          className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onCancel?.()}>取消</AlertDialogCancel>
          <button
            type="button"
            data-testid="admin-token-save"
            onClick={() => {
              const token = value.trim() || null;
              if (token) lsSet(ADMIN_TOKEN_KEY, token);
              onSave(token);
            }}
            className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            保存
          </button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
