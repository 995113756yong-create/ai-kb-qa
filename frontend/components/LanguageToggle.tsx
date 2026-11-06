"use client";

// 语言切换：与 ThemeToggle 并排放在同一处。
// 只有两种语言，直接做成切换按钮（不弹菜单），点击在 zh / en 之间来回切。

import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export default function LanguageToggle() {
  const { locale, setLocale, t } = useI18n();
  const next = locale === "zh" ? "en" : "zh";

  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label={t("language.switch")}
      title={next === "en" ? "English" : "中文"}
      onClick={() => setLocale(next)}
      className="gap-1.5 px-2 text-xs"
    >
      <Languages className="h-4 w-4" />
      <span className="tabular-nums">{locale === "zh" ? "中" : "EN"}</span>
    </Button>
  );
}