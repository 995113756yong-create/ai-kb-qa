"use client";

// 管理员令牌录入对话框：首次访问需要 admin 权限的接口时弹出。
// 令牌存 localStorage（key: kb-admin-token），不落 URL。

import { useState } from "react";

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
import { useI18n } from "@/lib/i18n";

export type AdminTokenDialogProps = {
  open: boolean;
  /** 用户保存令牌后回调（新令牌或 null 表示清除） */
  onSave: (token: string | null) => void;
  onCancel?: () => void;
};

export const ADMIN_TOKEN_KEY = "kb-admin-token";

export function AdminTokenDialog({ open, onSave, onCancel }: AdminTokenDialogProps) {
  const { t } = useI18n();
  const [value, setValue] = useState("");

  // 打开时从本地读一次初值。用「上一次的 open」判断是否刚打开，
  // 避免 effect 里无条件 setState（react-hooks/set-state-in-effect）。
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) setValue(lsGet(ADMIN_TOKEN_KEY) ?? "");
  }

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("experts.adminToken")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("experts.adminTokenHint")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <input
          data-testid="admin-token-input"
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("experts.adminTokenPlaceholder")}
          className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onCancel?.()}>{t("common.cancel")}</AlertDialogCancel>
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
            {t("common.save")}
          </button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
