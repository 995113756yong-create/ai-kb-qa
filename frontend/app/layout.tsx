import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI 知识库问答",
  description: "基于知识库的 Agent 问答系统：多步检索、证据引用、流式回答",
};

// 不用 Next 生成的全局 LayoutProps 类型：它是 next dev/build 后才写入的类型，
// CI 里先跑 tsc --noEmit 时还不存在，会报 Cannot find name 'LayoutProps'
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        {children}
      </body>
    </html>
  );
}
