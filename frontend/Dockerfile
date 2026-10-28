# 多阶段构建：只把 standalone 产物带进运行镜像
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# GitHub runner 到 npm registry 偶发 ECONNRESET（exit 152），
# 调大重试次数与超时，避免整次构建因为一次网络抖动作废
RUN npm config set fetch-retries 8 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 600000 \
 && npm ci --prefer-offline --no-audit

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# 构建阶段内存不够时容易 OOM，显式提高上限
ENV NODE_OPTIONS=--max-old-space-size=3072
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# standalone 产物自带最小化的 node_modules 与 server.js
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

USER node
EXPOSE 3000
CMD ["node", "server.js"]
