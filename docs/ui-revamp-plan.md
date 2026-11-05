
# ai-kb-qa 实现文档：前端视觉与体验全面升级（U1 + U2 + U3）

> **交给本地 AI 编程工具执行的唯一文档**。按顺序实现，全部完成后提交一个 PR。
> 基线：`main@9d994b2`。分支：`feat/ui-revamp`。
> 配套方案说明见《ai-kb-qa前端视觉与体验升级方案.md》（只是背景参考，**以本文档为准**）。

---

## 0. 目标、范围与通用规则

### 0.1 做完后的效果

1. 访问 `/`：一屏**演示首页**，有极光背景、产品定位、自动播放的问答回放动画、三项核心指标（取自真实评测），以及「试试健身教练」按钮。
2. 访问 `/chat`：**三栏工作台**。
   - 左栏：专家切换、历史会话、知识库。
   - 中间：对话区。回答按 Markdown 渲染，带可点击的引用标签、分阶段研究时间线、信任环和消息操作栏。
   - 右栏：**证据面板**，显示原文片段及前后相邻片段，命中片段高亮，并对照标出数字。
3. 访问 `/eval`：**评测看板**，展示严格模式与参考模式的指标对比、各分类通过率、延迟与 token 消耗，以及未通过用例。
4. 在任意页面按 `⌘K` / `Ctrl+K` 打开**命令面板**。支持浅色、深色、跟随系统三种主题。移动端可用。
5. 刷新页面后会话还在；切换专家不再清空对话；每个专家有自己的历史会话列表。

### 0.2 范围边界

- **不改 AI 逻辑**：检索、ReAct 循环、证据登记、句子级溯源、阈值、回答模式等行为全部保持不变。后端只做第 2 节列出的**增量**改动。
- BFF 转发层 `app/api/[...path]/route.ts` 只做转发，不加业务逻辑；新接口全部经它转发。
- 不引入前端状态管理库（Redux/Zustand 等），用 React hooks 和 Context 即可。

### 0.3 通用规则（必须遵守）

1. 每完成一个小节就运行一次相关测试；最终 `cd backend && pytest`、`cd frontend && npm run lint && npm run typecheck && npm test && npm run build` 全部通过。
2. **现有测试**：保留语义，行为确实变化时才修改断言，并在 PR 描述里逐条说明原因。不允许为了通过测试而删除测试。
3. 保留现有 `data-testid`（清单见第 10.1 节）；组件重写时把 testid 挂到语义相同的新元素上。
4. 安全：禁止 `dangerouslySetInnerHTML`；Markdown 渲染设置 `skipHtml`；外链加 `target="_blank" rel="noopener noreferrer"`；不渲染用户输入中的 HTML。
5. 依赖：安装时用当前最新稳定版，并锁进 `package-lock.json`。如果遇到 peer 依赖冲突（React 19 / Next 16），优先换兼容版本，**禁止** `--force`；确实需要 `--legacy-peer-deps` 时在 PR 中说明。
6. 代码注释用中文，解释「为什么」，不复述代码。
7. 提交按第 13.2 节的顺序拆成多个 commit，最后合成一个 PR。

---

## 1. 准备

### 1.1 依赖

```bash
cd frontend
# 组件底座（shadcn 会自动安装 radix-ui / class-variance-authority / clsx / tailwind-merge / tw-animate-css 等）
npx shadcn@latest init        # 选 New York 风格、zinc 基色、CSS variables: yes
npx shadcn@latest add button dialog alert-dialog dropdown-menu popover hover-card tooltip \
  sheet command toggle-group tabs scroll-area separator badge skeleton textarea input label \
  radio-group progress sonner

npm i lucide-react motion react-markdown remark-gfm rehype-highlight highlight.js \
  next-themes idb-keyval recharts geist
npm i -D fake-indexeddb
```

说明：
- `cmdk` 会随 shadcn 的 `command` 组件一起安装。
- 字体用 `geist` 包（本地字体文件），**不用** `next/font/google`。CI 的 Docker 构建已经有过网络抖动的问题，构建期下载字体会引入新的失败点。
- `fake-indexeddb` 只在测试里使用（见第 5.2 节）。

### 1.2 shadcn 初始化后的检查

- `components.json` 的别名为 `@/components`、`@/lib/utils`，与现有 `tsconfig` 的 `@/*` 一致。
- shadcn 会改写 `app/globals.css`。按第 3.1 节**合并**，不要直接覆盖：现有的 `.thin-scroll`、`.brand-gradient`、`.thinking-dot`、`.message-enter` 要保留。
- 新生成的 `components/ui/*` 文件**不写测试**，但要能通过 lint 和 typecheck。

### 1.3 目标目录结构

```
frontend/
├── app/
│   ├── layout.tsx                 # Providers：主题、Toaster、Tooltip、字体
│   ├── page.tsx                   # 演示首页（服务端组件）
│   ├── chat/page.tsx              # 工作台入口：读 searchParams → <ChatApp initial…/>
│   ├── eval/page.tsx              # 评测看板（服务端组件，读 data/eval-summary.json）
│   └── api/[...path]/route.ts     # 不变
├── components/
│   ├── ui/                        # shadcn 生成
│   ├── ChatApp.tsx                # 工作台根组件（保留文件名，测试直接渲染它）
│   ├── ChatInput.tsx              # 输入框（保留文件名与原有 props，扩展新 props）
│   ├── AgentTrace.tsx             # 研究时间线（保留文件名，重写内部）
│   ├── AnswerView.tsx             # 溯源视图（保留现有按句渲染逻辑）
│   ├── SourceCards.tsx            # 出处标签行（保留文件名与 testid）
│   ├── MessageList.tsx            # 消息列表（保留文件名）
│   ├── DocSidebar.tsx             # 删除或改为对 workspace/AppSidebar 的再导出（见第 6.2 节）
│   ├── providers/
│   │   ├── AppProviders.tsx
│   │   └── AdminTokenDialog.tsx
│   ├── workspace/
│   │   ├── AppSidebar.tsx
│   │   ├── ExpertSwitcher.tsx
│   │   ├── ConversationList.tsx
│   │   ├── KnowledgePanel.tsx
│   │   ├── UploadZone.tsx
│   │   ├── EmptyState.tsx
│   │   ├── AssistantMessage.tsx
│   │   ├── AnswerMarkdown.tsx
│   │   ├── CitationChip.tsx
│   │   ├── TrustRing.tsx
│   │   ├── MessageActions.tsx
│   │   ├── EvidencePanel.tsx
│   │   ├── ExpertGallery.tsx
│   │   ├── CreateExpertWizard.tsx
│   │   ├── CommandPalette.tsx
│   │   ├── ThemeToggle.tsx
│   │   └── TopBar.tsx
│   ├── landing/
│   │   ├── Hero.tsx
│   │   ├── DemoReplay.tsx
│   │   ├── FeatureGrid.tsx
│   │   └── ArchitectureStrip.tsx
│   └── eval/
│       ├── KpiCards.tsx
│       ├── CategoryChart.tsx
│       ├── LatencyChart.tsx
│       └── FailureTable.tsx
├── lib/
│   ├── api.ts / sse.ts / types.ts / chat.ts / answer.ts   # 已有，按需扩展
│   ├── utils.ts                   # shadcn 的 cn()
│   ├── storage.ts                 # 会话存储（IndexedDB / 内存回退）
│   ├── conversations.ts           # 会话的纯函数：命名、归一化、分组
│   ├── phases.ts                  # 研究阶段推断
│   ├── citations.ts               # remark 插件：[n] / [E3] → 引用节点
│   ├── numbers.ts                 # 数字抽取与高亮切片
│   ├── personaTemplates.ts        # 新建专家的人设模板
│   ├── evalSummary.ts             # 评测 JSON 的类型与读取
│   └── hooks/
│       ├── useAgents.ts
│       ├── useDocs.ts
│       ├── useConversations.ts
│       ├── useAgentRun.ts
│       ├── useHotkeys.ts
│       └── useElapsed.ts
└── data/
    └── eval-summary.json          # 评测看板数据（提交进仓库）
```

---

## 2. 后端增量改动

全部保持向后兼容：只新增字段和接口，不修改已有字段的含义。

### B1. 出处补 `chunk_id`

`backend/app/agent/evidence.py` 的 `_to_source` 增加一个字段：

```python
"chunk_id": meta.get("chunk_id"),
```

测试（`tests/test_citation.py` 新增）：`finalize` 产出的每个 source 都带 `chunk_id`，值等于登记文档的 `metadata["chunk_id"]`。

### B2. 读取片段及其相邻片段

`backend/app/main.py` 新增接口：

```
GET /api/chunks/{chunk_id}?agent_id=<id>&window=1
```

- 校验 `chunk_id`：`^[0-9a-f]{32}:\d{1,6}$`（`doc_id` 是 `uuid4().hex`，见 `DOC_ID_RE`），不匹配返回 422。
- `window` 限制在 0~2，默认 1。
- 通过 `_agent_kb(request, agent_id)` 取知识库，调用 `kb.get_neighbors(chunk_id, window)`。结果为空时返回 404 `{"detail": "片段不存在或文档已删除"}`。
- 只读接口，**不需要**管理员口令，但要加限流：复用 `limiter.check(client_key(request))`。
- 响应：

```json
{
  "status": "ok",
  "chunk_id": "…:3",
  "doc_id": "…",
  "source": "新手训练计划.txt",
  "items": [
    {"chunk_id": "…:2", "chunk_index": 2, "page": null, "content": "…", "is_target": false},
    {"chunk_id": "…:3", "chunk_index": 3, "page": null, "content": "…", "is_target": true},
    {"chunk_id": "…:4", "chunk_index": 4, "page": null, "content": "…", "is_target": false}
  ]
}
```

测试（`tests/test_api.py`）：正常返回 3 条且中间一条 `is_target=true`；窗口在文档首尾时自然截断；非法 ID 返回 422；不存在返回 404；`agent_id` 隔离——用 A 专家的 chunk_id 查 B 专家返回 404。

### B3. 专家推荐问题 `starter_questions`

`backend/app/agent_store.py`：
- `DEFAULT_AGENT` 增加 `"starter_questions": []`。
- `create()` 新增参数 `starter_questions: Optional[List[str]] = None`：去掉首尾空格和空串，最多 4 条，每条不超过 60 字；超出时截断，不报错。
- `list_agents()` / `get()` 对缺少该字段的旧条目补默认值 `[]`（与 `answer_mode` 的补全方式一致）。
- 新增 `patch(agent_id, **fields)`：只允许 `starter_questions` 一个键，在锁内更新并 `_save()`。**本次不开放 HTTP 接口**，只给播种迁移使用。

`backend/app/main.py`：`AgentCreateRequest` 增加 `starter_questions: List[str] = Field(default_factory=list, max_length=4)`，透传给 `store.create`。

`backend/app/seed_agents.py`：
- 新增常量：

```python
FITNESS_STARTERS = [
    "新手一周练几次比较合适？",
    "增肌每天要吃多少蛋白质？",
    "零基础怎么开始跑步？",
    "深蹲的动作要点有哪些？",
]
```

- 新建健身专家时传入 `starter_questions=FITNESS_STARTERS`。
- **迁移已有部署**：健身专家已存在、但条目里没有 `starter_questions` 键时，调用 `store.patch(FITNESS_AGENT_ID, starter_questions=FITNESS_STARTERS)`。如果条目里已有该键（即使是空列表），说明是用户的选择，不覆盖。

测试（`tests/test_agents_platform.py`）：创建时截断到 4 条；旧清单缺字段时列表返回 `[]`；播种迁移只补缺失的字段，不覆盖已有值。

### B4. 专家列表返回 `doc_count`

`GET /api/agents` 的每个条目增加 `doc_count: int`：
- 如果该专家的 KnowledgeBase 已缓存在 `store._kbs`（default 专家用 `app.state.kb`），取 `len(kb.list_documents())`。
- 否则**直接读** `<index_dir>/docs.json` 的 `docs` 长度，**不要**为了计数去构造 KnowledgeBase（那会加载 FAISS）。文件不存在或解析失败时返回 0。
- 封装为 `AgentStore.doc_count(agent_id) -> int`。default 专家的 index_dir 用构造参数里的 `index_dir`。

测试：上传 2 份文档后 `doc_count == 2`；新专家为 0；构造一份损坏的 `docs.json` 时返回 0 且不抛异常。

### B5. 回答反馈

```
POST /api/feedback
```

请求体（Pydantic）：

```python
class FeedbackRequest(BaseModel):
    agent_id: str = Field(DEFAULT_AGENT_ID, max_length=32)
    question: str = Field(..., min_length=1, max_length=1000)
    answer: str = Field(..., min_length=1, max_length=8000)
    rating: Literal["up", "down"]
    reason: str = Field("", max_length=500)
    mode: Optional[Literal["strict", "reference"]] = None
    grounded_ratio: Optional[float] = Field(None, ge=0, le=1)
```

- 限流（复用 `limiter`），**不需要**口令。
- 专家不存在时返回 404。
- 追加一行写入该专家日志目录下的 `feedback.jsonl`（default 专家用 `agent_log_dir`，其他用 `store.log_dir_of(agent_id)`）。字段为请求体内容加 `ts`。写失败只记 warning，仍返回 `{"status": "ok"}`。
- 日志里**不记录** IP。

测试：写入一行、字段正确；`rating` 非法返回 422；专家不存在返回 404；写失败（日志目录不可写，用 monkeypatch 模拟）时仍返回 200。

### B6. 检索命中明细 + 研究阶段事件

**命中明细（给时间线画相关度条形图用）**

`backend/app/agent/tools.py` 的 `search_kb` 在返回结果里增加：

```python
"hits": [
    {"evidence_id": ev.evidence_id, "source": meta.get("source"), "page": meta.get("page"), "score": score}
    for ev, score in zip(evidences, scores)
]
```

- `backend/app/agent/runner.py`：在把工具结果交给模型之前执行 `hits = result.pop("hits", None)`，**`to_text(result)` 中不包含 hits**，避免给模型的 token 变多、prompt 内容发生变化。`tool_result` 事件里增加可选字段 `"hits": hits`（仅 search_kb 有）。运行日志 `steps` 不写 hits。
- `backend/app/mcp_server.py`：同样在输出前 `pop("hits", None)`，保持 MCP 输出与改动前完全一致。
- `scores` 字段的语义保持现状，**不改**。

**阶段事件（可选开关，默认关闭）**

`run_agent(..., emit_phases: bool = False)`。为 True 时，在以下位置额外 yield `{"type": "phase", "phase": <name>}`：

| phase | 时机 |
|-------|------|
| `research` | 进入研究循环前（包括查询拆解之前）；知识库为空的路径不发 |
| `answer` | 任何路径第一次输出 `answer_delta` 之前（包括严格模式的固定拒答、无证据兜底回答） |
| `verify` | 正常证据路径中，流式输出结束后、调用 `finalize` / 溯源之前 |

`main.py` 的生产路径传 `emit_phases=True`。

测试：
- 现有 `test_agent.py` 的事件序列断言**不受影响**（默认关闭）。
- 新增 `test_runner_phases.py`：开启后，正常路径的 phase 依次为 research → answer → verify；严格拒答路径为 research → answer；空知识库路径只有 answer。
- 新增测试：search_kb 的 tool_result 事件带 hits，且传给模型的 tool 消息内容里不包含 `"hits"`。

### B7. 评测导出 JSON

`eval/run_eval.py` 增加参数 `--json PATH`。写入结构如下（类型定义在第 8.1 节）：

```json
{
  "generated_at": "2026-11-03T05:25:03Z",
  "title": "Agent 评测报告",
  "commit": "<git rev-parse --short HEAD 的结果，取不到时为 null>",
  "source": "run_eval",
  "modes": { "strict": { "...": "summarize() 原样输出" }, "reference": { "...": "..." } },
  "cases": [
    {"id": "f1", "mode": "strict", "category": "fact", "agent": "default",
     "passed": true, "elapsed_ms": 9123, "grounded_ratio": 1.0, "faithfulness": 0.9}
  ],
  "failures": [
    {"id": "m3", "mode": "strict", "category": "multi_hop", "question": "…", "reason": "…"}
  ]
}
```

- `modes[*]` 直接使用 `summarize()` 的返回值，**不改**它的键名。
- `failures[*].reason` 与 markdown 报告「未通过用例」一节使用同一套逻辑。如果该逻辑目前写在 `format_report` 内部，先提取为函数 `failure_reason(r) -> str`，两处共用。
- `--mock` 模式下也能导出（便于测试），此时 `source` 为 `"mock"`。

**初始数据**：本次不重新跑真实评测（会产生费用）。请根据现有 `eval/report.md` 的数字**手工整理**出 `frontend/data/eval-summary.json`：`modes` 和 `failures` 照实填写，`cases` 填空数组，`source` 写 `"eval/report.md@e5d6a39"`。百分比换算成 0~1 的小数，延迟换算成毫秒。

测试（新建 `backend/tests/test_eval_export.py`，或放在 eval 目录下用 pytest 能收集到的位置）：`--mock --json tmp.json` 生成的文件包含 `modes.strict.pass_rate`，`failures` 是列表。

### B8. 文档同步

README 的「接口」一节补充：`GET /api/chunks/{chunk_id}`、`POST /api/feedback`、`starter_questions` / `doc_count` 字段、`tool_result.hits`、`phase` 事件。

---

## 3. 设计系统

### 3.1 `app/globals.css`

把 shadcn 生成的变量与现有样式合并。关键 token（OKLCH 写法，以 shadcn 的格式为准，下表只说明意图）：

| Token | 浅色 | 深色 | 用途 |
|-------|------|------|------|
| `--background` | zinc-50 `#fafafa` | `#09090b` | 页面背景 |
| `--card` | `#ffffff` | `#111113` | 卡片、消息气泡 |
| `--primary` | indigo-500 `#6366f1` | indigo-400 | 主按钮、焦点环 |
| `--brand-from` / `--brand-to` | `#6366f1` / `#8b5cf6` | 同 | 品牌渐变（保留） |
| `--kb` | emerald-500 | emerald-400 | 知识库依据 |
| `--general` | amber-500 | amber-400 | 一般知识 |
| `--doubt` | rose-500 | rose-400 | 数字存疑 |
| `--radius` | `1rem` | 同 | 卡片圆角；按钮用 `calc(var(--radius) - 4px)` |

在 `@theme inline` 中暴露 `--color-kb`、`--color-general`、`--color-doubt`，组件里直接写 `text-kb`、`bg-general/10` 这样的工具类。

新增样式：

```css
/* 极光背景：只在深色模式和首页使用，透明度低，避免抢内容 */
.aurora {
  background:
    radial-gradient(60% 50% at 20% 0%, rgb(99 102 241 / 0.18), transparent 70%),
    radial-gradient(50% 40% at 85% 10%, rgb(139 92 246 / 0.14), transparent 70%);
}
/* 网格底纹：首页 hero 用 */
.grid-bg {
  background-image: linear-gradient(to right, rgb(120 120 130 / 0.08) 1px, transparent 1px),
                    linear-gradient(to bottom, rgb(120 120 130 / 0.08) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse at center, black 40%, transparent 75%);
}
/* 渐变描边：证据面板命中片段、首页卡片悬停 */
.ring-gradient { /* 使用 border-image 或伪元素实现 1px 渐变描边 */ }
/* 研究阶段脉冲 */
@keyframes pulse-ring { 0% { box-shadow: 0 0 0 0 rgb(99 102 241 / .45); } 100% { box-shadow: 0 0 0 8px rgb(99 102 241 / 0); } }
.pulse-ring { animation: pulse-ring 1.4s ease-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .thinking-dot, .message-enter, .pulse-ring { animation: none; }
}
/* 代码块：两种主题都用深色底 */
.prose-answer pre { /* 圆角、内边距、横向滚动 */ }
```

引入 `highlight.js/styles/github-dark.css`（只在 `AnswerMarkdown` 中 import）。

### 3.2 字体

`app/layout.tsx`：

```tsx
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
// <html className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`} suppressHydrationWarning>
```

`body` 的字体栈：`var(--font-geist-sans), "PingFang SC", "Microsoft YaHei", system-ui, sans-serif`。数字统一使用 `tabular-nums`（计时器、指标、百分比）。

### 3.3 Providers

`components/providers/AppProviders.tsx`（客户端组件）：

```tsx
<ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
  <MotionConfig reducedMotion="user">
    <TooltipProvider delayDuration={200}>
      <AdminTokenProvider>
        {children}
        <Toaster richColors position="top-center" />
      </AdminTokenProvider>
    </TooltipProvider>
  </MotionConfig>
</ThemeProvider>
```

- 深色模式改用 class 策略：所有组件的 `dark:` 写法保持不变，但 Tailwind 4 需要在 globals.css 中声明 `@custom-variant dark (&:where(.dark, .dark *));`（shadcn init 通常已写好，检查一下）。
- `layout.tsx` 的 metadata：title 为 `AI 知识库问答 · 可信的专家工作台`，补充 `openGraph`（标题、描述）。

### 3.4 图标映射（替换 emoji）

| 原 emoji | lucide 图标 |
|----------|-------------|
| 🔍 search_kb | `Search` |
| 📄 read_chunk | `FileText` |
| 🗂 list_documents | `Library` |
| 🛠 其他工具 | `Wrench` |
| 📎 出处 | `Paperclip` |
| ⚠️ 警告 | `TriangleAlert` |

专家头像继续使用 `agent.emoji`，放在渐变底的圆角方块里。

---

## 4. 路由与页面

| 路由 | 类型 | 内容 |
|------|------|------|
| `/` | 服务端组件 | 演示首页（第 7 节） |
| `/chat` | 服务端外壳 + 客户端 `ChatApp` | 工作台 |
| `/eval` | 服务端组件 + 懒加载图表 | 评测看板（第 8 节） |

`app/chat/page.tsx`：

```tsx
export default async function ChatPage({ searchParams }: { searchParams: Promise<{ agent?: string; c?: string }> }) {
  const sp = await searchParams;
  return <ChatApp initialAgentId={sp.agent} initialConversationId={sp.c} />;
}
```

- `ChatApp` **不使用** `useSearchParams` / `useRouter`，只通过 props 接收初始值。状态变化时用 `window.history.replaceState(null, "", "/chat?agent=…&c=…")` 同步地址栏。这样组件测试不需要 mock Next 路由。
- 旧书签 `/` 不再进入工作台：首页的主按钮足够醒目，README 中的演示链接同时给出 `/` 和 `/chat`。

---

## 5. 工作台状态重构

现在的 `ChatApp.tsx` 有 432 行，状态和渲染混在一起。重构为「hooks 管状态，组件只负责渲染」。

### 5.1 视图模型扩展（`lib/chat.ts`）

```ts
export type Step =
  | { kind: "decompose"; key: string; queries: string[] }
  | { kind: "thought"; key: string; text: string }
  | { kind: "tool_call"; key: string; name: string; args: ToolCallArgs }
  | { kind: "tool_result"; key: string; name: string; ok: boolean; summary: string; hits?: SearchHit[] };

export type Phase = "understand" | "research" | "read" | "answer" | "verify" | "done";

// assistant 消息新增字段：
//   createdAt: number            // 计时器起点
//   phase: Phase                 // 当前阶段
//   question: string             // 对应的用户问题（重新生成、反馈用）
//   feedback: "up" | "down" | null
//   usage: UsageInfo | null
// user 消息新增：createdAt: number

export type Conversation = {
  id: string;            // crypto.randomUUID()
  agentId: string;
  title: string;         // 首个问题前 24 字；可重命名
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
};
```

同步更新 `chat.ts` 顶部的注释：会话现在按专家保存，切换专家时切换到对应专家的会话列表，不再清空。

`lib/types.ts`：
- `Source` 增加 `chunk_id?: string | null`。
- `AgentInfo` 增加 `starter_questions?: string[]`、`doc_count?: number`。
- `AgentCreateRequest` 增加 `starter_questions?: string[]`。
- 新增 `SearchHit = { evidence_id: string; source: string | null; page: number | null; score: number }`。
- `ToolResultEvent` 增加 `hits?: SearchHit[]`。
- 新增 `PhaseEvent = { type: "phase"; phase: "research" | "answer" | "verify" }`，并加入 `AgentEvent` 联合类型。
- 新增 `ChunkResponse`、`FeedbackRequest` 类型（与第 2 节对应）。

### 5.2 会话存储（`lib/storage.ts`）

```ts
export interface ConversationStore {
  list(agentId: string): Promise<Conversation[]>;   // 按 updatedAt 倒序
  get(id: string): Promise<Conversation | null>;
  put(conv: Conversation): Promise<void>;
  remove(id: string): Promise<void>;
}
export function createIdbStore(): ConversationStore;   // idb-keyval，独立 store：createStore("kbqa", "conversations")
export function createMemoryStore(): ConversationStore;
export function getDefaultStore(): ConversationStore;  // 没有 indexedDB（SSR）时回退内存
```

规则：
- 每个专家最多保留 50 个会话，`put` 时淘汰最旧的。
- 单个会话最多 200 条消息，超出时提示「会话过长，建议新建会话」，但不截断已有消息。
- 写入前调用 `conversations.ts` 的 `normalizeForSave`：`running` 改为 false；正在运行的消息标记 `stopped=true`，并对 answer 执行 `stripRawCitations`。
- 读取后调用 `normalizeOnLoad`：兼容旧结构，缺失字段补默认值。
- **测试**：`vitest.setup.ts` 引入 `import "fake-indexeddb/auto";`，用 IDB 实现和内存实现跑同一组用例。

`lib/conversations.ts`（纯函数，全部写单测）：
- `makeTitle(question)`：去掉换行，取前 24 字，超出加「…」。
- `groupByDate(convs, now)`：分为今天 / 昨天 / 近 7 天 / 更早。
- `normalizeForSave`、`normalizeOnLoad`。

### 5.3 Hooks

| Hook | 职责 |
|------|------|
| `useAgents()` | 拉取专家列表，提供 `refresh`、`create`、`remove`；错误时返回空列表并 toast 一次 |
| `useDocs(agentId)` | 拉取文档列表，提供上传队列（见第 6.4 节）和删除 |
| `useConversations(agentId, store)` | 当前专家的会话列表、当前会话、`newConversation` / `select` / `rename` / `remove` / `updateMessages`；写入防抖 500ms，收到 final 时立即写入 |
| `useAgentRun()` | 发起一次问答（Agent 走 SSE，快速模式走 `/api/ask`），停止、重新生成；把事件归约为消息补丁（`reduceEvent(message, event)` 是纯函数，单独测试） |
| `useHotkeys(map)` | 全局快捷键；在输入框、textarea 中只响应带修饰键的组合 |
| `useElapsed(startMs, running)` | 运行中每 100ms 刷新一次已用时间 |

**流式渲染节流**：`useAgentRun` 把 `answer_delta` 先放进缓冲区，用 `requestAnimationFrame` 每帧最多合并刷新一次 state。现在每个 delta 都触发一次渲染，Markdown 渲染开销更大时会卡顿。测试环境没有 rAF 时回退为同步刷新。

**事件归约 `reduceEvent`**（覆盖并扩展现有的 switch 逻辑）：
- `step`：phase 至少为 `research`。
- `tool_call`：名称为 search_kb 时 phase 设为 `research`，read_chunk 时设为 `read`。
- `tool_result`：保存 hits。
- `phase`：直接设置。
- `answer_delta`：phase 至少为 `answer`。
- `final`：phase 设为 `done`，写入 answer、sources、segments、groundedRatio、answerMode、usage、elapsedMs。
- `error`：与现有逻辑一致。
- 未知的事件类型：忽略（向前兼容）。

阶段只前进、不后退：`phases.ts` 定义顺序 `understand < research < read < answer < verify < done`，提供 `advance(cur, next)`。注意 `read` 之后再次检索时，**显示**为 research 进行中，但已完成的阶段标记不回退。实现方式：阶段条根据「已到达过的最大阶段」和「当前活动阶段」两个值分别渲染。

### 5.4 切换专家与会话

- 切换专家：中止正在进行的生成，加载该专家最近一次会话；没有会话时显示空状态。不再清空其他专家的会话。
- 新建会话按钮：在当前专家下创建一个空会话。会话在发出第一个问题时才落盘，避免产生空会话。
- 文档被删除后，历史会话里的引用仍能显示（source 自带 `content`），证据面板请求相邻片段返回 404 时显示「原文已删除，仅显示当时的引用片段」。

---

## 6. 组件规格

### 6.1 整体布局（`ChatApp`）

```
≥ xl（1280）  ：| 左栏 288px | 对话区 自适应（内容最大宽度 760px 居中） | 证据面板 380px（打开时） |
md ~ xl      ：| 左栏 288px | 对话区 |，证据面板改为右侧 Sheet 覆盖
< md         ：左栏改为左侧 Sheet（顶栏汉堡按钮打开）；证据面板改为底部 Sheet（高度 70vh）
```

- `TopBar`：玻璃质感（`bg-background/70 backdrop-blur-xl border-b`）。左侧是 Logo（渐变方块 + 「AI 知识库问答」，点击回到 `/`）、当前专家名称和模式标签；中间是 `⌘K 搜索…` 伪输入框（点击打开命令面板）；右侧依次为「评测看板」链接、主题切换和 GitHub 图标链接。
- 深色模式下对话区顶部叠加 `.aurora`（`pointer-events-none absolute inset-x-0 top-0 h-64`）。
- 证据面板的开合使用 motion 的 `AnimatePresence` + 宽度/位移过渡，时长 200ms。

### 6.2 左栏 `AppSidebar`

从上到下分三块：

1. **ExpertSwitcher**：显示当前专家的大按钮（emoji 头像、名称、`doc_count` 份文档）。点击展开 DropdownMenu，列出全部专家（保留 `data-testid="agent-list"`、`agent-item-<id>`），底部有「专家广场…」和「新建专家…」两项。删除专家放在每个条目的悬停菜单里（default 不显示），用 AlertDialog 二次确认，文案「删除后该专家的文档、索引和会话记录都会清除，无法恢复」。删除时同时清除本地该专家的会话。
2. **ConversationList**：顶部有「＋ 新会话」按钮（`data-testid="new-conversation"`），下面按日期分组列出会话；当前会话高亮。悬停时显示「重命名 / 删除」（重命名在原位变为输入框，回车保存）。为空时显示「还没有会话」。
3. **KnowledgePanel**：标题为「知识库 · N」，可以折叠。内容包括 UploadZone 和文档列表：文件类型图标（pdf/md/txt 用不同颜色）、文件名（截断，悬停显示全名）、`chunks 片 · 大小 · 相对时间`；删除按钮在悬停时出现，删除前用 AlertDialog 确认。

原 `DocSidebar.tsx` 的职责拆进上述组件。原文件删除；如果测试直接引用了它，就保留为一个再导出的薄壳，并在 PR 中说明。

### 6.3 新建专家向导 `CreateExpertWizard` + 专家广场 `ExpertGallery`

**ExpertGallery**：一个 Dialog（大尺寸，`max-w-4xl`），以卡片网格展示（`sm:2 列 lg:3 列`）。每张卡片包含：
- 渐变封面条：根据 agent_id 的哈希从 6 组预设渐变中选一组，保证同一专家每次显示同一个颜色。
- emoji 头像、名称、描述（两行截断）、`回答模式` 标签、`N 份文档`。
- 「开始对话」按钮。

最后一张是虚线边框的「＋ 新建专家」卡片。

**CreateExpertWizard**：Dialog，三步，顶部有步骤指示器。

| 步骤 | 字段 | 校验 |
|------|------|------|
| ① 基本信息 | 名称（必填，≤40）、emoji（提供 12 个候选，点选，也可自己输入）、简介（≤200）、欢迎语（≤200） | 名称为空时不能进入下一步 |
| ② 人设与模式 | 人设模板卡片（选中后填入人设 textarea，可再编辑，≤2000）、回答模式（RadioGroup，保留 `answer-mode-fieldset`、`mode-strict`、`mode-reference`）、推荐问题（最多 4 条，逐条输入） | — |
| ③ 资料 | UploadZone（多文件）；可以跳过 | — |

- 第 ② 步完成时调用 `createAgent`；第 ③ 步的上传以新的 agent_id 为目标；完成后关闭弹窗，切换到新专家并新建会话，toast「专家已创建」。
- 保留 testid：`create-agent-button`（入口按钮）、`create-agent-form`（向导容器）、`agent-name-input`、`agent-persona-input`、`agent-submit`（第 ② 步的「创建」按钮）。
- `lib/personaTemplates.ts` 提供 4 个模板：健身教练（参考模式）、产品客服（严格模式）、法务助理（严格模式，强调「不构成法律意见」）、学习导师（参考模式）。每个模板包括 `name`、`emoji`、`persona`、`answer_mode`、`starter_questions`。人设文本的写法参照 `seed_agents.FITNESS_PERSONA`：给出说话风格、边界和风险提醒。

### 6.4 上传 `UploadZone`

- 支持拖拽（`onDragEnter/Over/Leave/Drop`）和点击选择（保留 `data-testid="file-input"` 的隐藏 input），支持一次选多个文件。拖入时虚线框高亮并显示「松开即可上传」。
- 客户端预校验扩展名（.txt/.md/.pdf）和大小（≤10MB，与后端 `MAX_UPLOAD_MB` 默认值一致，常量 `MAX_UPLOAD_MB` 放在 `lib/api.ts`），不通过时用 toast 说明原因，不发请求。
- 上传队列逐个串行上传，每项显示：
  - **上传中**：真实的字节进度。`lib/api.ts` 新增 `uploadDocWithProgress(file, agentId, onProgress)`，用 `XMLHttpRequest` 的 `upload.onprogress` 实现；fetch 拿不到上传进度。
  - **处理中**：字节上传完、等待响应期间，显示不确定进度条，文案「切分与向量化中…」。
  - **完成**：显示「✓ 已切分 N 个片段」，3 秒后从队列中移除，同时刷新文档列表。
  - **失败**：显示错误文案和「重试」按钮。
- 401 时走管理员口令流程（第 6.12 节），拿到口令后自动重试。
- 对话区为空状态时，整块区域也是拖拽目标，拖入时显示全屏半透明遮罩「拖到这里上传到 <专家名> 的知识库」。

### 6.5 空状态 `EmptyState`

当前会话没有消息时，在对话区居中显示：
- 专家大头像（64px，渐变底、柔和阴影）、名称、简介。
- 欢迎语气泡（有 greeting 时）。保留现有测试「专家 greeting 展示在空会话态」的断言文本。
- 推荐问题：2×2 网格的卡片按钮（`data-testid="starter-<i>"`），点击直接发送。来源为 `agent.starter_questions`；为空时使用通用默认问题：
  - 有文档：「知识库里有哪些文档？」「帮我总结一下最新上传的文档」「文档里最重要的三个结论是什么？」
  - 没有文档：「你能做什么？」，再加一张引导卡片「上传文档，让我基于你的资料回答」（点击打开文件选择）。
- 没有文档时保留现有的「基于一般知识」提示文案（对应测试「没有文档时也能对话…」）。

### 6.6 消息 `MessageList` / `AssistantMessage`

**用户消息**：右对齐，渐变气泡（保留 `.brand-gradient`），最大宽度 85%。

**助手消息** `AssistantMessage`（保留 `data-testid="assistant-<id>"`）结构：

```
┌ 头部：专家头像(20px) · 专家名 · [TrustRing] · [模式标签] · ……… [耗时 9.2s] ┐
│ AgentTrace（研究时间线，第 6.7 节）                                           │
│ 提示条（按需）：未引用提示 / 一般知识程序声明 / 已停止 / 错误                     │
│ 正文：阅读视图 AnswerMarkdown  或  溯源视图 AnswerView                          │
│ SourceCards（出处标签行）                                                     │
└ MessageActions（复制 / 重新生成 / 👍 / 👎 / 视图切换）                          ┘
```

- 卡片：`bg-card border rounded-2xl rounded-tl-md shadow-sm`，内边距 16px。
- **程序声明**（解决参考模式下声明正确率只有 37.5% 的问题）：`answerMode === "reference"` 且 segments 中存在 `kind === "general"` 时，在正文上方显示琥珀色提示条（`data-testid="general-knowledge-notice"`）：「部分内容来自一般知识（N 句），不在知识库中。」后面带一个「在溯源视图中查看」的按钮，点击切换到溯源视图。
- **未引用提示**：没有 segments 且 `grounded === false` 时，保留原有的 `ungrounded-warning` 和文案「该回答未引用文档内容，请谨慎参考」。
- **思考中**：没有 answer 且正在运行时，显示 3 行 Skeleton 加时间线，取代原来的「思考中…」三点动画（`.thinking-dot` 改给时间线的当前阶段使用）。
- 已停止 `stopped-hint`、错误 `role="alert"` 的语义保持不变，样式改为 shadcn Alert 风格。
- 自动滚动：保留最新提交中「贴底才跟随」的逻辑（`followRef`），并新增「回到底部」浮动按钮：用户上翻超过 200px 时出现，点击平滑滚到底部。

### 6.7 研究时间线 `AgentTrace`（重写）

保留 `data-testid="trace-toggle"`、`trace-steps` 和 props（`steps`、`running`、`elapsedMs`、`defaultOpen`），新增 props `phase`、`maxPhase`、`createdAt`。

**折叠态（一行）**：五个阶段点 + 连线：

```
●──●──◉──○──○   检索 2 次 · 阅读上下文 1 次        ⏱ 7.4s
理解 检索 阅读 撰写 校验
```

- 已完成的阶段：实心点加对勾，颜色为 primary。
- 当前阶段：`.pulse-ring` 脉冲。
- 未到达的阶段：空心点。
- 运行中计时器实时走秒（`useElapsed`，显示一位小数，`tabular-nums`）；完成后显示 `elapsedMs`。
- 整个研究过程中都没有调用 read_chunk 时，「阅读」阶段显示为跳过状态（虚线空心点），不影响后续阶段。

**展开态**：竖直时间线，每个 step 一个节点。
- thought：灰色斜体文本，最多 3 行，可展开。
- tool_call：图标 + 工具名称中文（search_kb 显示「检索」，read_chunk 显示「阅读上下文」，list_documents 显示「查看文档列表」）+ 参数。search_kb 的 query 显示为药丸标签。
- tool_result：成功/失败标记 + summary；有 `hits` 时显示**相关度条形图**，每条一行：`[E3] 新手训练计划.txt  ▇▇▇▇▇▇▁▁ 0.78`。条长按本次 hits 中的最大值归一化，颜色为 primary 的渐变。
- decompose：显示「拆解为 N 个子问题」和问题列表。
- 节点按顺序带进场动画（motion，stagger 40ms）。

**展开/折叠策略**：运行中、回答出现之前默认展开；收到第一个 `answer_delta` 时自动折叠（用户手动操作过之后，以用户的选择为准，沿用现有的 `manualOpen` 逻辑）。

### 6.8 信任环 `TrustRing`

- 28px 的 SVG 环形图：底圈为 muted 色，前景弧长等于 `groundedRatio`。颜色规则：≥0.8 为 kb 绿，≥0.4 为 general 琥珀，其余为 muted。中心显示百分比数字（10px，`tabular-nums`）。
- 保留 `data-testid="trust-badge"`（容器）和 `kb-ratio`（百分比文本），文本格式保持 `知识库依据 {n}%（{kb}/{total} 句）`，可以放在视觉隐藏或 Tooltip 内，但 testid 元素中必须包含该文本，满足现有断言。
- HoverCard 中的明细：知识库句 X、一般知识句 Y、中性句 Z、存疑数字 W，以及图例（绿点=知识库、琥珀点=一般知识、红色波浪线=数字存疑）。原来写在徽标里的图例文字移到这里。
- 存在 warnings 时，环旁边显示红色小标签 `⚠ N`（保留 `data-testid="numeric-warning"`，文本中包含「处数字未在出处中找到」）。
- 模式标签：严格模式用 indigo 色，参考模式用 sky 色，Tooltip 中解释两种模式的区别。
- `groundedRatio` 为 null 时不显示环，只显示模式标签。

### 6.9 回答正文

**阅读视图 `AnswerMarkdown`**（默认）：

```tsx
<ReactMarkdown
  skipHtml
  remarkPlugins={[remarkGfm, remarkCitations]}
  rehypePlugins={[rehypeHighlight]}
  components={{ a: SafeLink, "cite-ref": CitationChipAdapter, table: ScrollableTable, code: CodeBlock }}
>
  {text}
</ReactMarkdown>
```

- `lib/citations.ts` 中的 `remarkCitations` 插件：遍历 mdast 的 `text` 节点（**跳过** `inlineCode` / `code` / `link` 内部），把 `[n]` 拆分为 `{ type: "citeRef", data: { hName: "cite-ref", hProperties: { index: n, pending: false } } }`。流式阶段把模型原文中的 `[E3]`、`【E3】`、`[E1, E3]`、`[E1-E3]` 拆分为 `pending: true` 的节点，正则复用 `lib/answer.ts` 的 `RAW_CITATION_RE`，导出后共用。
- `[1][2]` 这类连续写法在没有链接定义时 remark 会把它当作文本，插件需要正确拆成两个节点。**必须为此写单测**。
- `CitationChip`：
  - 已映射：圆形数字标签。悬停 300ms 后用 HoverCard 显示预览（文件名 · 页码、snippet 前 120 字、「点击查看原文」）；点击打开证据面板。`aria-label="查看出处 n"`，与现有一致。
  - pending：灰色、不可点击的小标签，显示 `…`，`aria-hidden`。
- 正文排版类 `.prose-answer`（不要引入 `@tailwindcss/typography`，手写约 40 行即可）：段落间距、列表缩进、表格边框与横向滚动、行内代码底色、代码块（右上角有复制按钮）、引用块左侧色条。
- 流式容错：未闭合的 `**`、`` ` `` 和代码块围栏由 react-markdown 自然处理，不额外补全；只保证不抛异常（写测试：渲染 `"**加粗未闭合"` 和 `"```py\nprint(1)"` 都不报错）。
- 性能：`AnswerMarkdown` 用 `memo` 包裹，按 `text` 比较；插件数组定义为模块级常量。

**溯源视图 `AnswerView`**：保留现有按 segments 渲染的逻辑与测试。样式调整为：一般知识句使用 `bg-general/10` 加琥珀色下划线；存疑数字用 `decoration-doubt decoration-wavy underline`；引用标签改用 `CitationChip`。

**视图切换**：在 MessageActions 中用 ToggleGroup 切换「阅读 / 溯源」（`data-testid="view-reading"`、`view-trace"`）。只有存在 segments 时才显示该开关；没有 segments 时始终使用阅读视图。偏好保存在 localStorage `kbqa_answer_view`，对所有消息生效。

**快速模式（/api/ask）** 的回答同样使用 AnswerMarkdown 渲染，没有时间线和信任环。

### 6.10 出处标签行 `SourceCards`

- 从纵向列表改为**横向可换行的标签行**，标题为「出处 · N」（Paperclip 图标），可折叠，默认展开。
- 每个标签（保留 `id="source-<n>"`、`data-testid="source-card-<n>"`）：序号圆点 + 文件名（截断）+ 页码。悬停时显示 snippet 的 HoverCard，点击打开证据面板并定位到该出处。
- 从回答中的引用点击跳转时，对应标签闪烁高亮 1 秒（保留现有 `jumpToSource` 的语义）。

### 6.11 证据面板 `EvidencePanel`

状态：`{ messageId, index } | null`，保存在 ChatApp 中。`Esc` 关闭面板。

内容：

```
┌ 头部：[n] 文件名 · 第 p 页          [◀ 上一个出处] [下一个出处 ▶] [✕] ┐
│ 出处切换标签：[1] [2] [3]（本条回答的全部 sources）                      │
│ ── 上一片段（muted 色，可折叠）                                        │
│ ▌命中片段（左侧 3px 渐变色条 + 浅 primary 底）                          │
│ ▌…其中与引用句共有的数字用 <mark> 高亮…                                 │
│ ── 下一片段（muted 色）                                                │
│ 底部：引用它的句子（来自 segments 中 citations 包含 n 的句子，最多 3 句）  │
└───────────────────────────────────────────────────────────────────┘
```

- 数据：先用 `source.content`（没有时用 `snippet`）立即渲染命中片段。有 `chunk_id` 时调用 `getChunk(chunk_id, agentId, 1)`（新增到 `lib/api.ts`）获取相邻片段，结果按 chunk_id 缓存在内存 Map 中。加载中显示 Skeleton。返回 404 时显示提示「原文已删除，仅显示当时的引用片段」。没有 `chunk_id`（升级前的历史会话）时不发请求。
- **数字对照**：`lib/numbers.ts` 提供 `extractNumbers(text): string[]`（匹配整数、小数、百分比、区间如 `8-12`、`1.6-2.2`）和 `highlightSlices(content, numbers)`（返回 `{text, mark}[]` 切片，供 React 渲染，**不拼接 HTML**）。用「引用它的句子」中出现的数字，在命中片段里高亮。
- 底部「引用它的句子」中，带 warnings 的句子标出红色波浪线，便于人工核对。
- 布局：≥xl 时为内联第三栏，md~xl 时为右侧 Sheet，<md 时为底部 Sheet。
- 无障碍：作为 Sheet 时由 Radix 管理焦点；作为内联栏时使用 `role="complementary"` 和 `aria-label="证据面板"`。

### 6.12 管理员口令 `AdminTokenDialog`

- `lib/api.ts` 新增：

```ts
type TokenRequester = () => Promise<string | null>;
let requester: TokenRequester | null = null;
export function registerAdminTokenRequester(fn: TokenRequester | null): void { requester = fn; }
```

  `withAdminRetry` 遇到 401 时，优先调用 `requester`；没有注册时**回退到 `window.prompt`**（保持 `api.test.ts` 现有两个用例通过）。
- `AdminTokenProvider` 在挂载时注册 requester：打开 Dialog，内容包括口令输入框（`type="password"`）、说明「写操作（上传 / 删除 / 新建专家）需要管理员口令，口令只保存在本浏览器」，以及「取消 / 确认」按钮。用 Promise 返回结果。
- 新增测试：注册 requester 后 401 会调用它而不是 prompt；requester 返回 null 时抛出原错误。

### 6.13 输入框 `ChatInput`（Composer）

保留文件名和现有 props（`disabled`、`running`、`onSend`、`onStop`），保留 `chat-input`、`send-button` 两个 testid 和现有 5 个测试的行为（Enter 发送、Shift+Enter 换行、输入法组字时 Enter 不发送、空内容不发送、运行中按钮变成停止、禁用状态）。

新增可选 props：`mode`、`onModeChange`、`answerMode`、`placeholder`、`inputRef`。

外观为浮动卡片：`rounded-2xl border bg-card shadow-lg`，距底部 16px，宽度与内容区对齐。
- textarea 自动增高（1~8 行），不再使用 `resize-y`。
- 左下角：模式 ToggleGroup「Agent / 快速」（`data-testid="mode-agent"`、`mode-fast`，取代原顶部的 `mode-select`），两项都带 Tooltip 说明。旁边是当前专家的回答模式标签（只读）。
- 右下角：字数统计（超过 800 字后显示 `n/1000`，超过 1000 字禁止发送并标红，与后端 `max_length=1000` 一致）和发送/停止按钮（圆形，渐变；停止时显示方块图标）。
- 输入框下方的提示：`Enter 发送 · Shift+Enter 换行 · ⌘K 命令`，仅桌面端显示。

原顶部的模式栏删除。`ChatApp.test.tsx` 中「快速问答模式」用例改为点击 `mode-fast`，并在 PR 中说明。

### 6.14 消息操作栏 `MessageActions`

只在消息生成完成后显示（运行中隐藏）；桌面端悬停在消息上时淡入，最新一条消息常显，移动端常显。

| 按钮 | 行为 | testid |
|------|------|--------|
| 复制 | 复制纯文本：answer 去掉 `[n]` 后，再附加「\n\n出处：\n[1] 文件名 第p页 …」，成功后 toast「已复制」 | `action-copy` |
| 重新生成 | 用 `message.question` 重新发起请求，**替换**这条助手消息（不追加新的用户消息） | `action-regenerate` |
| 👍 | 调用 `sendFeedback`（rating=up），按钮高亮，toast「感谢反馈」 | `action-up` |
| 👎 | 打开 Popover，提供可选原因（「答非所问 / 事实错误 / 引用不准 / 其他」+ 文本框），提交后调用 `sendFeedback`（rating=down） | `action-down` |
| 阅读 / 溯源 | 见第 6.9 节 | `view-reading` / `view-trace` |

反馈状态写入 `message.feedback` 并持久化，同一条消息只能反馈一次（可以从 up 改为 down，每次修改都发送一条请求）。

### 6.15 命令面板 `CommandPalette`

`⌘K` / `Ctrl+K` 打开（shadcn `CommandDialog`）。工作台和首页都挂载该面板：首页只有「导航」和「主题」两组，工作台显示全部分组。

| 分组 | 条目 |
|------|------|
| 操作 | 新建会话、新建专家、上传文档、切换阅读/溯源视图 |
| 专家 | 全部专家（选中后切换） |
| 会话 | 当前专家的会话标题，支持模糊搜索（cmdk 内置），选中后打开 |
| 文档 | 当前专家的文档，选中后展开知识库面板并滚动高亮该文档 |
| 导航 | 首页、工作台、评测看板、GitHub 仓库 |
| 主题 | 浅色 / 深色 / 跟随系统 |

其他快捷键：`/` 聚焦输入框（焦点不在输入框时）、`Esc` 关闭证据面板或停止生成（无弹层打开时，按一次停止生成并 toast 提示）、`⌘⇧O`（Windows 为 `Ctrl+Shift+O`）新建会话。快捷键清单放在命令面板底部。

### 6.16 Toast 与错误

- 全部改用 sonner：上传成功或失败、删除、创建专家、复制、反馈、网络错误。
- 每条助手消息自身的错误仍显示在消息内（`role="alert"`），不弹 toast，避免重复。
- 后端不可用（502）时，顶栏下方显示一条可关闭的横幅「后端服务暂不可用，正在重试…」，每 10 秒请求一次 `/api/health`，恢复后自动消失。

---

## 7. 演示首页（`/`）

服务端组件。只有 `DemoReplay` 和 `Hero` 中的动画部分是客户端组件。**不调用任何后端接口**。

### 7.1 结构

1. **导航条**：Logo、「评测看板」「GitHub」链接、主题切换和「进入工作台」按钮。
2. **Hero**（`.grid-bg` + `.aurora` 背景）：
   - 小标签：「RAG + 手写 ReAct Agent」
   - 主标题（`text-4xl md:text-6xl font-semibold tracking-tight`，关键词用品牌渐变文字）：**每一句回答，都有据可查**
   - 副标题：「多步检索、逐句溯源、评测驱动的知识库问答。上传文档，或直接和内置的健身教练聊聊。」
   - 按钮：主按钮「试试健身教练 →」（`/chat?agent=fitness-coach`），次按钮「上传我的文档」（`/chat`），文字链接「查看评测报告」（`/eval`）。
   - 右侧（桌面端）或下方（移动端）放 `DemoReplay`。
3. **指标条**：三个大数字，读取 `data/eval-summary.json`：
   - 严格模式整体通过率（`modes.strict.pass_rate`）
   - 忠实度（`modes.strict.faithfulness`）
   - 检索命中率（`modes.strict.retrieval_rate`）

   数字从 0 滚动到目标值（客户端组件，遵守 reduced-motion）。下方小字注明「基于 36 条评测用例 · 生成于 {generated_at}」，用例数取 `modes.strict.total`。
4. **FeatureGrid**：三张卡片，带图标、标题、两行说明，悬停时显示渐变描边：
   - 「多步检索」：Agent 自己决定检索什么、检索几次，向量与 BM25 混合召回。
   - 「逐句溯源」：程序登记证据编号，回答逐句标注来源，编造的引用会被剔除。
   - 「评测驱动」：双模式评测、LLM 评判忠实度，每项取舍都有数据支撑。
5. **ArchitectureStrip**：横向流程图（纯 CSS 实现，节点加箭头）：`浏览器 → Next.js BFF → FastAPI → ReAct Agent → FAISS + BM25 → LLM`。节点悬停时显示一句职责说明。移动端改为纵向排列。
6. **技术栈徽章墙**：Next.js 16、React 19、TypeScript、Tailwind 4、FastAPI、FAISS、DeepSeek、Docker、GitHub Actions、Sealos。
7. **页脚**：GitHub 链接和「个人作品，仅供演示」。

### 7.2 `DemoReplay`（问答回放动画）

用一段**写死**的脚本模拟一次完整问答，循环播放（每轮约 10 秒，播完停 3 秒再重播）：

1. 用户气泡出现：「新手一周练几次比较合适？」
2. 时间线依次点亮：理解 → 检索（显示 query 标签「新手 每周 训练 频率」，相关度条出现）→ 撰写。
3. 回答逐字打出：「新手建议**每周训练 3 次**，隔天进行[1]；每次包含热身 5-10 分钟[1]……」
4. 信任环从 0 增长到 100%，出处标签 `[1] 新手训练计划.txt` 浮入。
5. 光标悬停在 `[1]` 上，弹出预览卡片。

**脚本里的文本必须与 `seed_agents.py` 的健身语料一致**（上面的例句都来自《新手训练计划.txt》）。实现方式：
- 复用工作台的 `AgentTrace`、`AnswerMarkdown`、`TrustRing`、`SourceCards` 组件，传入伪造的 props，保证首页演示的样子与真实界面一致。
- 计时用 `setTimeout` 链；页面不可见（`document.hidden`）时暂停。
- `prefers-reduced-motion` 时直接显示最终状态，不播放动画。

---

## 8. 评测看板（`/eval`）

### 8.1 数据（`lib/evalSummary.ts`）

```ts
export type ModeSummary = {
  total: number; errors: number;
  retrieval_rate: number; answer_rate: number; citation_rate: number; reject_rate: number; pass_rate: number;
  avg_ratio: number | null; numeric_consistency: number | null; faithfulness: number | null;
  latency_p50: number; latency_p95: number; avg_tokens: number;
  price_in: number; price_out: number;
  by_category: Record<string, { n: number; pass_rate: number }>;
};
export type EvalSummary = {
  generated_at: string; title: string; commit: string | null; source: string;
  modes: Partial<Record<"strict" | "reference", ModeSummary>>;
  cases: Array<{ id: string; mode: string; category: string; agent: string; passed: boolean;
                 elapsed_ms: number; grounded_ratio: number | null; faithfulness: number | null }>;
  failures: Array<{ id: string; mode: string; category: string; question: string; reason: string }>;
};
import raw from "@/data/eval-summary.json";
export const evalSummary = raw as EvalSummary;
```

`tsconfig.json` 需要开启 `resolveJsonModule`（检查是否已开启）。

### 8.2 页面布局

1. **页头**：标题、生成时间、commit、数据来源；「如何复现」折叠块，内含命令 `python -m eval.run_eval --base … --judge --out eval/report.md --json frontend/data/eval-summary.json`。
2. **KpiCards**：用 Tabs 或并排两列展示 strict / reference 两种模式，每种模式 6 张卡片：整体通过率、忠实度、引用合法率、拒答/声明正确率、平均知识库依据比例、平均 token/题。每张卡片显示两种模式的差值箭头（例如参考模式比严格模式低 11.1pp）。**每张卡片要有一句说明**，例如在拒答/声明正确率旁注明「参考模式下该指标衡量『声明来源』是否正确，现已改为程序声明，见工作台」。
3. **CategoryChart**：分组柱状图，横轴为分类（fact / compare / precise / multi_hop / reject / mixed / derived / persona），两组柱子分别是两种模式的通过率，Tooltip 显示用例数。
4. **LatencyChart**：P50 / P95 的分组柱状图。`cases` 非空时，额外画出每条用例的耗时散点或直方图；为空时不显示这一块，并注明「明细需重新运行评测导出」。
5. **FailureTable**：未通过用例表，列为模式、ID、分类、问题、原因；可按模式筛选。
6. **方法说明**：简要介绍两层评测、五项判定和评测集的设计思路（可以从 README 的「评测」一节提炼），末尾链接到仓库中的 `eval/`。

- 图表组件通过 `next/dynamic` 并设置 `ssr: false` 懒加载 recharts，加载时显示 Skeleton。
- 颜色：strict 用 indigo，reference 用 sky，与工作台的模式标签保持一致。
- 某个模式缺失时，只显示存在的模式。

---

## 9. 移动端与无障碍

- 断点按第 6.1 节。顶栏在移动端只保留汉堡按钮、专家名、⌘K 图标和主题切换。
- 输入框吸底：`pb-[env(safe-area-inset-bottom)]`；textarea 字号不小于 16px，避免 iOS 聚焦时页面缩放。
- 所有可点击元素的触控区域不小于 40×40px（引用标签视觉上可以小，但要通过 padding 扩大点击区域）。
- 颜色之外必须有第二种区分方式：一般知识句除了底色还有下划线，存疑数字除了颜色还有波浪线，信任环中心有百分比数字。
- 键盘：Tab 顺序合理；弹层焦点由 Radix 管理；引用标签可以用键盘聚焦，按 Enter 打开证据面板。
- `prefers-reduced-motion`：关闭脉冲、进场、数字滚动和回放动画。
- 对比度：正文文字对背景至少 4.5:1；深色模式下 muted 文字不低于 zinc-400。

---

## 10. 测试计划

### 10.1 必须保留的 testid

`agent-list`、`agent-item-<id>`、`agent-name-input`、`agent-persona-input`、`agent-submit`、`answer-mode-fieldset`、`mode-strict`、`mode-reference`、`chat-input`、`send-button`、`create-agent-button`、`create-agent-form`、`file-input`、`kb-ratio`、`numeric-warning`、`trust-badge`、`ungrounded-warning`、`stopped-hint`、`trace-toggle`、`trace-steps`、`assistant-<id>`、`source-card-<n>`。

其中 `mode-select` 被 `mode-agent` / `mode-fast` 取代（第 6.13 节）。

### 10.2 现有测试的处理

| 文件 | 处理 |
|------|------|
| `ChatApp.test.tsx` | 保留全部 11 个用例的语义。需要修改的地方：快速模式改为点击 `mode-fast`；新建专家流程改为向导（先点「下一步」再点 `agent-submit`）；专家列表在 DropdownMenu 中，先点击 ExpertSwitcher 展开。渲染 `ChatApp` 时用 `AppProviders` 包一层（导出一个测试用的 `renderWithProviders` 工具函数）。 |
| `ChatInput.test.tsx` | 5 个用例应全部原样通过；只有「没有文档时禁用输入框」这一个用例，在 props 语义不变的前提下允许调整查询方式 |
| `stop.test.tsx` | 原样通过（停止后清除原始编号并显示已停止；停止后不误报错误） |
| `api.test.ts` / `route.test.ts` /