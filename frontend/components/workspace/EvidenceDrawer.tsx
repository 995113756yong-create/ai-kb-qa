"use client";

// 移动端证据抽屉：底部滑出，复用 EvidenceReader。
// 桌面端（lg 及以上）由 ChatApp 直接渲染右侧栏，不进这个组件。

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { EvidenceReader, type EvidenceReaderProps } from "@/components/workspace/EvidenceReader";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export type EvidenceDrawerProps = Omit<EvidenceReaderProps, "className"> & {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function EvidenceDrawer({ open, onOpenChange, ...readerProps }: EvidenceDrawerProps) {
  const { t } = useI18n();
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            "fixed inset-0 z-40 bg-black/40 lg:hidden",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          )}
        />
        <DialogPrimitive.Content
          data-testid="evidence-drawer"
          aria-describedby={undefined}
          className={cn(
            "fixed inset-x-0 bottom-0 z-50 flex h-[80dvh] flex-col rounded-t-2xl border-t border-border bg-card shadow-lg lg:hidden",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
          )}
        >
          <DialogPrimitive.Title className="sr-only">{t("evidence.title")}</DialogPrimitive.Title>

          {/* 抓手 */}
          <div className="flex shrink-0 items-center justify-center py-2">
            <span className="h-1 w-10 rounded-full bg-border" aria-hidden />
          </div>

          <DialogPrimitive.Close
            aria-label={t("evidence.closeDrawer")}
            className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </DialogPrimitive.Close>

          <div className="min-h-0 flex-1 overflow-hidden">
            <EvidenceReader {...readerProps} className="h-full" />
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export default EvidenceDrawer;
