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

type Props = {
  workspace?: boolean;
  onNewConversation?: () => void;
  onNewAgent?: () => void;
  /** 导航回调：返回 false 表示导航不可用（如测试环境），菜单项隐藏 */
  onNavigate?: (href: string) => void;
};

export default function CommandPalette({ workspace, onNewConversation, onNewAgent, onNavigate }: Props) {
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
        <CommandGroup heading="命令">
          {workspace ? (
            <>
              <CommandItem onSelect={() => { setOpen(false); onNewConversation?.(); }} data-testid="cmd-new-conversation">
                <MessageSquarePlus /> 新会话
              </CommandItem>
              <CommandItem onSelect={() => { setOpen(false); onNewAgent?.(); }} data-testid="cmd-new-agent">
                <CopyPlus /> 新建专家
              </CommandItem>
            </>
          ) : null}
        </CommandGroup>
        {onNavigate ? (
          <CommandGroup heading="导航">
            <CommandItem onSelect={() => go("/")} data-testid="cmd-home">
              <Home /> 首页
            </CommandItem>
            <CommandItem onSelect={() => go("/chat")} data-testid="cmd-chat">
              <MessageSquarePlus /> 工作台
            </CommandItem>
            <CommandItem onSelect={() => go("/eval")} data-testid="cmd-eval">
              <BarChart3 /> 评测看板
            </CommandItem>
          </CommandGroup>
        ) : null}
        <CommandGroup heading="主题">
          <CommandItem onSelect={() => { setOpen(false); setTheme("light"); }} data-testid="cmd-theme-light">
            <Sun /> 浅色模式
          </CommandItem>
          <CommandItem onSelect={() => { setOpen(false); setTheme("dark"); }} data-testid="cmd-theme-dark">
            <Moon /> 深色模式
          </CommandItem>
          <CommandItem onSelect={() => { setOpen(false); setTheme(resolvedTheme === "dark" ? "light" : "dark"); }}>
            <Sun /> 跟随系统相反切换
          </CommandItem>
        </CommandGroup>
        <CommandList>
          <CommandEmpty>没有匹配的命令</CommandEmpty>
        </CommandList>
      </CommandDialog>
    </>
  );
}
