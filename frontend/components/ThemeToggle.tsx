"use client";

import { useTheme } from "next-themes";
import { Laptop, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export default function ThemeToggle() {
  const { t } = useI18n();
  const { theme, setTheme, resolvedTheme } = useTheme();
  // 水合前不能读 theme（服务端拿不到），必须先渲染一个占位再切到真实图标。
  // 这是 next-themes 官方文档推荐的标准写法，属于规则误报。
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- 水合标记，只执行一次
  useEffect(() => setMounted(true), []);

  const next = theme === "system" ? (resolvedTheme === "dark" ? "light" : "dark") : theme === "dark" ? "light" : "dark";
  const icon = !mounted ? (
    <Sun className="h-4 w-4" />
  ) : theme === "system" ? (
    <Laptop className="h-4 w-4" />
  ) : theme === "dark" ? (
    <Moon className="h-4 w-4" />
  ) : (
    <Sun className="h-4 w-4" />
  );

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={t("theme.toggle")}
      onClick={() => setTheme(next)}
      suppressHydrationWarning
    >
      {icon}
    </Button>
  );
}
