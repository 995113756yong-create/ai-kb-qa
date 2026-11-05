# UI Revamp 进度（交接文档）

分支：`feat/ui-revamp`（基于 main@9d994b2）
方案：`docs/ui-revamp-plan.md`（898 行完整版）
后端 B1-B8 已完成并提交（256 项测试全绿）。

## 当前状态（2026-11-05 更新）：约 78%

### 本轮完成
- **typecheck 全量清零**（此前 34 个错误：核心 15 + 旧测试 19）
- **测试 42 通过 / 5 失败**（此前 38 通过 / 12 失败）
- 修复 `UploadZone`：扩展为双模式组件——`mode="upload"`（默认，直接上传）与 `mode="local"`（仅选文件回调 `onFilesChange`，向导场景创建专家后再上传）
- 修复 `CreateExpertWizard`：UploadZone 调用改为本地模式（`mode="local" multiple`）
- 修复 `ExpertSwitcher`：新增 `onCreateAgent` prop 透传给 CreateExpertWizard，修复「新建专家按钮点了没反应」的断链
- 重写 `AppSidebar`：props 对齐 ChatApp 实际传参（`agentsLoading/currentId/onNewChat/onUpload/onDeleteDoc/onCreateAgent/onDeleteAgent/activeAgent`），内部桥接 ConversationList（`activeId/onSelect/onNew`）与 KnowledgePanel（`uploading/onUpload/onDelete`）
- `useDocs` 补 `remove(docId)` 方法（调 api.deleteDoc + refresh）
- `ChatApp`：补 `handleCreateAgent/handleDeleteAgent`（含 toast、刷新专家列表与文档列表、删除当前专家时回落 default）、`syncAddress` 声明顺序修复、`updateLast` 签名适配（内部做 `(m) => updater(m as ChatMessage & {role:"assistant"})` 转换）、补 `createAgent/deleteAgent` 导入
- 重写 `CommandPalette`：**去掉 useRouter**（违反方案 6.5「不用 Next 路由」，导致测试环境 app router 未挂载报错），改为 `onNavigate` 回调注入
- 重写旧测试 `ChatApp.test.tsx`（7 用例）与 `stop.test.tsx`（6 用例）至新架构：props 注入初始值、对象式 streamAgent mock、新事件协议（`event.type`：`step/thought/answer_delta/final`）

### 关键契约（后续开发必读）
- `AgentInfo` 必填字段：`agent_id/name/description/persona/greeting/emoji/model/answer_mode/created_at/builtin`（测试用 `mkAgent()` 工厂函数）
- `DocInfo` 字段名：`filename`（非 `name`）、`ext/size/chunks/uploaded_at`
- `AgentEvent` 类型：`step` 是 `number`（非对象）；`answer_delta` 无 `step` 字段；结束事件是 `final`（非 `done`），字段 `grounded_ratio`（snake_case）
- `ChatInput` 锚点：placeholder「提问…（Enter 发送，Shift+Enter 换行）」、`data-testid="chat-input"` / `send-button`
- 模式切换按钮：文本 `Agent` / `快速`（在 ChatApp 顶栏，非 ChatInput 内）
- `streamAgent(questionOrOptions, onEvent?, signal?, agentId?)` 双签名兼容；`useAgentRun.run({...params, message, update})` 对象式调用
- 专家切换下拉菜单项查询用 `role: "menuitem"`

### 剩余工作（约 22%）
1. **5 个测试运行时失败**（typecheck 已过，纯运行时断言问题）：
   - ChatApp.test.tsx 3 个：agent 模式答案未渲染（`final` 事件 mock 的字段可能需 `grounded_ratio` 或事件时序问题）、fast 模式按钮点击后 ask 未触发（「快速」按钮查询方式）、持久化断言
   - stop.test.tsx 2 个：停止流程时序（send-button 文本切换为「停止」的等待）
   - 排查方向：先在测试里打印 DOM（`screen.debug()`）确认实际渲染，再核对 `useAgentRun` 的 final 事件处理字段（`lib/useAgentRun.ts:152-180`）与 `flushAnswer` 缓冲逻辑
2. **剩余 workspace 组件**（方案清单里的，按需）：`AnswerMarkdown` 已建，核查 `MessageActions/TrustRing/CitationChip` 是否挂载到 MessageList
3. **3 个页面**：`app/page.tsx`（首页/落地）、`app/chat/page.tsx`（从 URL 读初始值传 ChatApp）、`app/eval/page.tsx`（评测看板，读 `eval-summary.json`）
4. **构建验证**：`npm run build` + 更新 `eval-summary.json`（含 commit 字段）
5. **PR**：feat/ui-revamp → main

### 已验证可用的命令
```powershell
cd D:\beacon-projects\ai-kb-qa\frontend
& npx tsc --noEmit          # typecheck
& npx vitest run            # 测试
& npm run build             # 构建（未跑）
```
