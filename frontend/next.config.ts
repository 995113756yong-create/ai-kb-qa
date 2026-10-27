import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 前端镜像只保留 standalone 产物，容器里直接 node server.js
  output: "standalone",
  // SSE 必须关闭压缩，否则事件会被 gzip 缓冲住、无法逐条送达
  compress: false,
  poweredByHeader: false,
  // 转发层需要显式的 runtime = "nodejs" 与 dynamic = "force-dynamic"，
  // 而 cacheComponents 不允许导出 route segment 配置，因此这里不启用它
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
