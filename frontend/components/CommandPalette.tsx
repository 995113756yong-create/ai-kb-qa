"use client";

// 命令面板（Cmd+K）：不用 Next 路由，导航回调注入（方案 6.5），避免测试环境 app router 未挂载报错。

import { CommandDialog, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { useTheme } from "next-themes";
import {
  BarChart3,
  CopyPlus,
  Home,
  MessageSquarePlus,
  Moon,
  Sun,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

type Props = {
  workspace?: boolean;
  onNewConversation?: () => void;
  onNewAgent?: () => void;
  /** 导航回调：返回 false 表示导航不可用（如测试环境），菜单项隐藏 */
  onNavigate?: (href: string) => void;
};

export default function CommandPalette({ workspace, onNewConversation, onNewAgent, onNavigate }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { setTheme, resolvedTheme } = useTheme();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      onNavigate?.(href);
    },
    [onNavigate],
  );

  return (
    <>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandGroup heading={t("palette.commands")}>
          {workspace ? (
            <>
              <CommandItem onSelect={() => { setOpen(false); onNewConversation?.(); }} data-testid="cmd-new-conversation">
                <MessageSquarePlus /> {t("palette.newChat")}
              </CommandItem>
              <CommandItem onSelect={() => { setOpen(false); onNewAgent?.(); }} data-testid="cmd-new-agent">
                <CopyPlus /> {t("palette.newExpert")}
              </CommandItem>
            </>
          ) : null}
        </CommandGroup>
        {onNavigate ? (
          <CommandGroup heading={t("palette.navigation")}>
            <CommandItem onSelect={() => go("/")} data-testid="cmd-home">
              <Home /> {t("palette.home")}
            </CommandItem>
            <CommandItem onSelect={() => go("/chat")} data-testid="cmd-chat">
              <MessageSquarePlus /> {t("palette.workbench")}
            </CommandItem>
            <CommandItem onSelect={() => go("/eval")} data-testid="cmd-eval">
              <BarChart3 /> {t("palette.evalBoard")}
            </CommandItem>
          </CommandGroup>
        ) : null}
        <CommandGroup heading={t("palette.themeGroup")}>
          <CommandItem onSelect={() => { setOpen(false); setTheme("light"); }} data-testid="cmd-theme-light">
            <Sun /> {t("palette.lightMode")}
          </CommandItem>
          <CommandItem onSelect={() => { setOpen(false); setTheme("dark"); }} data-testid="cmd-theme-dark">
            <Moon /> {t("palette.darkMode")}
          </CommandItem>
          <CommandItem onSelect={() => { setOpen(false); setTheme(resolvedTheme === "dark" ? "light" : "dark"); }}>
            <Sun /> {t("palette.toggleOpposite")}
          </CommandItem>
        </CommandGroup>
        <CommandList>
          <CommandEmpty>{t("palette.noResults")}</CommandEmpty>
        </CommandList>
      </CommandDialog>
    </>
  );
}
