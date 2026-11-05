# UI Revamp 实施记录（归档）

> 本文记录 UI 升级的实施过程与当时的决策，已于 `00d22f8` 合入 main。
> 后续工作见根目录 README 与 `docs/` 下的其他文档。

分支：`feat/ui-revamp`（基于 main@9d994b2）
方案：`docs/ui-revamp-plan.md`（898 行完整版）

## 状态：功能完整，测试与构建双绿

| 项 | 状态 |
|---|---|
| 后端 B1-B8 | 已完成（commit `ca6b868`） |
| 设计系统（Tailwind v4 + shadcn） | 完成 |
| 状态层（useConversations / useAgentRun / useAgents / useDocs / useHotkeys） | 完成 |
| 组件层（workspace 13 个 + ui 11 个） | 完成 |
| 三个页面（`/`、`/experts`、`/eval`） | 完成 |
| 测试 | 47/47 通过 |
| `tsc --noEmit` | 无错误 |
| `next build` | 成功，4 条路由 |

## 本轮修复的真实缺陷

### 1. 停止生成完全失效

`useAgentRun` 返回的 `cancel` 是 `cancelFlush` —— 只取消 rAF 缓冲，**从不 abort 请求**。
用户点「停止」后请求继续跑，按钮卡在「停止」。

修复：新增 `controllerRef`，`cancel` 同时 `abort()` + `cancelFlush()`。

### 2. 流式更新全部丢失

`ChatApp.updateLast` 闭包捕获发送那一刻的 `conversations` 状态。
首次发送时 `create()` 刚生成的会话尚未重渲染，`currentId` 仍为 `null`，
`if (!currentId) return` 把所有 `answer_delta` / `final` 静默丢弃 —— 用户看到永远「思考中」。

修复：改用 `runTargetRef` 记录本轮 `{convId, assistantId}`，
`updateLast` 只读 ref 不读 state。`stop` 时**不清空** ref（abort 后还要靠它写回 `stopped`）。

### 3. 持久化换存储会丢用户历史

初版用 IndexedDB（idb-keyval），与线上已有 localStorage 会话不兼容；
且 jsdom 无 `indexedDB`，组件测试拿不到落盘结果。

修复：`lib/store.ts` 改回 localStorage（key 前缀 `kbqa:conversations:`，按专家隔离）。

### 4. 测试 mock 与真实契约不符

`streamAgent` 真实签名支持对象式（`{question, onEvent, signal, agentId, mode}`）与位置参数两种，
但 stop 测试的 mock 只按位置参数取 `signal`，拿到 `undefined` → abort 永不触发。

修复：mock 同时兼容两种签名（`opts?.onEvent ?? onEvent`、`opts?.signal ?? positionalSignal`）。

### 5. fast 模式用例提交方式

点「快速」按钮后焦点离开输入框，`user.keyboard("[Enter]")` 不再触发提交。
修复：改用 `send-button` 提交。

## 评测看板数据 schema

`data/eval-summary.json` 的实际结构与方案第 9 节的初版草图不同，以实际产物为准：

```
{ generated_at, title, commit, source,
  modes: { strict|reference: {
    total, errors,
    retrieval_rate, answer_rate, citation_rate, reject_rate, pass_rate,
    avg_ratio, numeric_consistency, faithfulness,
    latency_p50, latency_p95, avg_tokens, price_in, price_out,
    by_category: { <cat>: { n, pass_rate } },
    cases: [{ id, question, category, mode, answer, problems, grounded, steps, sources }]
  } } }
```

`lib/evalTypes.ts` 与 `lib/evalSummary.ts` 已按此对齐（`pct`、`modeRows`、`categoryRates`、`failedCases`）。

## 状态

- 已通过合并提交 `00d22f8` 合入 main（含后端 B1-B8 与前端全量改造）
- 线上效果需重新部署 Sealos 前端；本地 `docker compose up -d` 可直接查看
- `eval-summary.json` 目前是 strict/reference 两种模式的 36 条用例

## 常用命令

```bash
cd frontend
npx vitest run          # 47 项测试
npx tsc --noEmit        # 类型检查
npx next build          # 生产构建
```
