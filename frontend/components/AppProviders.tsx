"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider } from "@/lib/i18n";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <I18nProvider>
        <TooltipProvider delayDuration={200}>
          {children}
          <Toaster position="top-center" richColors closeButton />
        </TooltipProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
