# AI 知识库问答系统（RAG + 手写 ReAct Agent）

上传文档后自动切分、向量化，再基于文档内容回答问题。系统提供两条问答路径：**固定 RAG**（一次检索）作为对照基线，**手写 ReAct Agent**（多步检索 + 证据引用 + 流式输出）作为主路径。

**在线演示**：https://suinlwijcdst.cloud.sealos.io

## 架构

```
浏览器
  │
  ▼
Next.js（App Router，端口 3000）
  ├─ 页面与交互：文档栏 / 对话区 / Agent 时间线 / 出处卡片
  └─ Route Handler  /api/[...path]  ── 纯转发，不做业务
        │  （请求体与响应体都以流的形式透传，SSE 逐条下发）
        ▼
FastAPI（端口 8000，全部 AI 逻辑在这里）
  ├─ 固定 RAG  /api/ask          检索 → Prompt → 模型 → 回答
  ├─ Agent     /api/agent/stream 手写 ReAct 循环 → SSE 事件流
  │     ├─ 研究阶段：模型决定调用 search_kb / read_chunk / list_documents
  │     └─ 回答阶段：只带已登记的证据，流式生成 + 引用校验
  ├─ 知识库    FAISS 索引 + docs.json 清单（进程内单例，带锁）
  └─ 运行日志  logs/agent_runs.jsonl（供离线评测）
```

前后端职责边界很清楚：**Python 负责全部 AI 逻辑，Next.js 只做界面和转发，不直接调用大模型。**

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Next.js 16（App Router）+ TypeScript（strict）+ Tailwind CSS |
| 前端测试 | Vitest + Testing Library（jsdom） |
| 后端框架 | FastAPI |
| Agent | 手写 ReAct 循环（不使用 LangChain 的 Agent 封装） |
| 模型接入 | 官方 openai SDK（兼容硅基流动等 OpenAI 协议服务） |
| RAG 工具链 | LangChain（文档加载、切分、FAISS 向量库） |
| 向量数据库 | FAISS |
| Embedding | BAAI/bge-large-zh-v1.5（硅基流动） |
| 对话模型 | Qwen/Qwen2.5-7B-Instruct（固定 RAG）/ Qwen/Qwen2.5-72B-Instruct（Agent） |
| 容器化 | Docker（后端 + 前端多阶段构建）+ docker compose |
| CI/CD | GitHub Actions |
| 云部署 | Sealos Cloud |

## 核心功能

- **多文档知识库**：多次上传追加到同一索引，服务启动时加载一次常驻内存；片段 ID 固定为 `doc_id:chunk_index`
- **固定 RAG**：FAISS 语义检索 Top-K，拼装带编号的上下文后由模型生成回答
- **Agent 多步检索**：模型自己决定检索什么、检索几次、要不要读上下文
- **回答带出处**：每个结论标注证据编号，引用由程序校验，可点击跳转到原文片段
- **不做无依据的回答**：没有检索到证据时直接回答"文档中未找到相关信息。"
- **流式输出**：思考过程、工具调用、回答增量都通过 SSE 实时推送
- **删除文档**：按文档整体删除片段并清理索引，删空后可从空库重建
- **安全加固**：上传文件由服务端重命名，限制类型与大小；删除接口校验 ID 格式；转发层拒绝路径穿越

## 项目结构

```
ai-kb-qa/
├── backend/
│   ├── app/
│   │   ├── config.py           # 环境配置
│   │   ├── document.py         # 加载、切分、KnowledgeBase（FAISS + docs.json）
│   │   ├── qa.py               # 固定 RAG 链与 QAService
│   │   ├── main.py             # 应用工厂 create_app + 全部 HTTP 接口
│   │   └── agent/
│   │       ├── llm.py          # AgentLLM 协议 + OpenAI 兼容实现
│   │       ├── tools.py        # 工具定义（JSON Schema）与执行
│   │       ├── evidence.py     # 证据登记表与引用校验
│   │       ├── prompts.py      # 系统提示词与回答提示词
│   │       ├── runner.py       # ReAct 循环，产出事件流
│   │       └── sse.py          # 事件 → SSE 文本、心跳、断连检测
│   ├── tests/                  # pytest（假 Embedding / 假 LLM，不访问外网）
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # 只渲染 <ChatApp />
│   │   └── api/[...path]/route.ts   # 转发层
│   ├── components/             # ChatApp / DocSidebar / MessageList / AgentTrace / AnswerView / SourceCards / ChatInput
│   ├── lib/                    # types / api / sse / chat
│   ├── __tests__/              # vitest
│   └── Dockerfile
├── docker-compose.yml
├── .github/workflows/docker-publish.yml
└── README.md
```

## 本地开发

### 方式一：docker compose（一条命令）

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 API Key

docker compose up --build
# 浏览器访问 http://localhost:3000
```

`web` 通过 `BACKEND_URL=http://api:8000` 找到后端；后端的数据目录挂载在本地，重启容器不丢知识库。

### 方式二：分别启动前后端

```bash
# 后端
cd backend
pip install -r requirements-dev.txt
cp .env.example .env            # 填入 API Key
uvicorn app.main:app --reload --port 8000
```

```bash
# 前端（另开一个终端）
cd frontend
npm install
cp .env.example .env            # 默认 BACKEND_URL=http://localhost:8000
npm run dev                     # 访问 http://localhost:3000
```

> 前端只监听 3000，后端只提供 API。后端不再托管任何静态资源，直接访问 `http://localhost:8000/` 会返回 404，这是预期行为。

## 环境变量

### 后端 `backend/.env`

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | — | 必填，模型服务 API Key（兼容旧名 `SILICONFLOW_API_KEY`） |
| `OPENAI_API_BASE` | `https://api.siliconflow.cn/v1` | OpenAI 兼容接口地址 |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh-v1.5` | 向量模型 |
| `CHAT_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 固定 RAG 的对话模型 |
| `AGENT_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | Agent 模型，必须支持 OpenAI 的 tools 调用 |
| `AGENT_MAX_STEPS` | `6` | 研究阶段最多调用几轮模型 |
| `AGENT_SEARCH_K` | `5` | `search_kb` 默认返回的片段数（`run_agent` 调用时会覆盖工具内的默认值） |
| `AGENT_LOG_DIR` | `backend/logs` | Agent 运行日志目录 |
| `MAX_UPLOAD_MB` | `10` | 单文件上传上限 |
| `TOP_K` | `3` | 固定 RAG 的检索片段数 |

### 前端 `frontend/.env`

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_URL` | `http://localhost:8000` | 转发层的后端地址，**运行时**读取，可在部署时切换 |

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/docs` | 已索引文档列表 |
| POST | `/api/upload` | 上传文档并追加到索引（multipart/form-data） |
| DELETE | `/api/docs/{doc_id}` | 删除文档（`doc_id` 必须是 32 位小写十六进制） |
| POST | `/api/ask` | 固定 RAG 问答 |
| POST | `/api/agent/stream` | Agent 问答，SSE 流式返回 |

`/api/ask` 返回：

```json
{
  "status": "ok",
  "question": "报销流程是什么？",
  "answer": "报销需先提交申请，再由主管审批 [1]。",
  "sources": [
    {"index": 1, "doc_id": "3f2a…", "source": "财务制度.pdf", "page": 2, "snippet": "第三条 报销申请…"}
  ]
}
```

### SSE 事件

`POST /api/agent/stream`，请求体 `{"question": "..."}`（1～1000 字），响应 `text/event-stream`。
每个事件格式为 `event: <type>\ndata: <json>\n\n`，`data` 里同样带 `type` 字段，前端可直接复用类型定义。

| 事件 | data 字段 |
|------|-----------|
| `step` | `step` |
| `thought` | `step`, `text` |
| `tool_call` | `step`, `id`, `name`, `args` |
| `tool_result` | `step`, `id`, `name`, `ok`, `summary` |
| `answer_delta` | `text`（原始文本，可能带 `[E3]` 这种编号） |
| `final` | `answer`（已重编为 `[1]`）、`sources`、`grounded`、`steps`、`elapsed_ms` |
| `error` | `detail` |

响应头带 `Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Connection: keep-alive`；15 秒没有事件时下发一行 `: ping` 心跳；客户端断开后立即停止，不再调用模型。

## Agent 设计

这一节是整套实现里最需要讲清楚的部分。

### 1. 为什么手写 ReAct 循环

- LangChain 的 Agent 封装把「什么时候停」「错误怎么回给模型」「重复调用怎么拦」都藏在内部，出问题时只能读源码，面试时也讲不清具体行为。手写循环的每一步都是显式代码，可以直接指着 `runner.py` 说明。
- 手写后三件关键事情都变成可控的普通逻辑：**停止条件**（见第 4 点）、**错误回灌**（工具异常不抛出，转成 `{"error": ...}` 交给模型自己修正）、**证据登记**（在工具层登记编号，而不是解析模型输出）。
- 依赖面更小：只用到 `openai` 这一个 SDK 做模型调用，LangChain 仅保留文档加载、切分和 FAISS 这些确定性的工具链。

### 2. 为什么分成「研究」和「回答」两个阶段

| | 研究阶段 | 回答阶段 |
|---|---|---|
| 是否给工具 | 给（`tool_choice=auto`） | 不给 |
| 是否流式 | 否 | 是 |
| 提示词约束 | 怎么检索、怎么标注证据 | 只能用已列出的证据作答 |

好处：
- **提示词各管一件事**。带工具时模型容易一边调工具一边输出半成品文本，两件事混在一个提示词里互相干扰。
- **回答能稳定流式输出**。研究阶段不带流，回答阶段一次 `stream=True` 请求，前端拿到的是干净的增量文本。
- **引用只能来自已登记的证据**。回答阶段模型看不到新文档，能引用的编号一定在研究阶段登记过，防幻觉的边界由此确定。

代价是**多调用一次模型**（研究若干轮 + 回答一轮），并且研究阶段无法向前端流式显示 token。前端用「步骤时间线 + 最终流式回答」来抵消这个体验损失。

### 3. 证据编号与引用校验如何防幻觉

三层防护，从弱到强：

1. **让模型引用短编号而不是长 ID**。检索结果给模型时标注 `[E1]`、`[E2]`，而不是 `3f2a…:7` 这种长串。编号越短，模型写错的概率越低。
2. **编号由程序分配，不由模型生成**。`EvidenceRegistry` 在工具返回片段时分配编号，同一片段（`chunk_id` 相同）重复出现沿用原编号。模型只能引用已经发出去的编号。
3. **最终回答再校验一次**。`finalize()` 用正则扫出回答里的 `[E数字]`：
   - 登记表里不存在的编号**直接删掉**——模型编造的引用不会留在正文里；
   - 有效编号按首次出现顺序**重编为 `[1]`、`[2]`**，`sources` 与正文编号严格对应；
   - 一个括号里写多个编号（`[E1, E2]`、`[E1、E2]`——模型的实际写法）会合并成 `[1][2]`，重复编号去重；
   - 没有任何有效引用的回答，`grounded=false`，前端显示黄色提示「该回答未引用文档内容，请谨慎参考」。「未找到」类回答本身不需要引用，仍算 `grounded=true`。

这样即使模型幻觉，最坏结果是「回答被标黄」或「编造的引用被删」，而不是「引用指向一份不存在的文档」。

### 4. 停止条件

循环有四个独立出口，任一条满足都进入回答阶段：

| 条件 | 阈值 | 代码位置 |
|---|---|---|
| 模型主动停止 | 返回的 `tool_calls` 为空 | `if not turn.tool_calls: break` |
| 达到最大步数 | `AGENT_MAX_STEPS`（默认 6） | `for step in range(1, max_steps + 1)` |
| 重复调用拦截 | 参数规范化后完全相同 | 命中后返回「结果同上」，不执行检索 |
| 连续工具错误 | 3 次 | `consecutive_errors >= MAX_CONSECUTIVE_ERRORS` |

另外还有两个兜底：
- **没有证据**：模型不调工具就停止，`registry` 为空 → 直接回「文档中未找到相关信息。」，不再调用模型生成回答（省一次调用，也避免它凭常识瞎答）。
- **知识库为空**：直接返回提示，完全不调用模型。

重复调用拦截用 `name + sort_keys 规范化后的参数 JSON` 做键，`{"query":"A","k":5}` 和 `{"k":5,"query":"A"}` 视为同一个调用——模型很爱在参数顺序上反复试探。

### 5. 已知取舍与边界

**限定文档检索必须放大候选**。FAISS 的 `filter` 是「先取 `fetch_k` 条再筛」，不是按条件检索。原来用 `fetch_k=k*4`，只要另一份文档够大就会把候选占满，目标文档一条都筛不出来——「对比两份文档」这个核心场景会直接失效。现在传了 `doc_id` 时把 `fetch_k` 放到索引总量。

**算向量不占锁**。上传要先调 Embedding 接口（几百毫秒到数秒）。如果在全局锁里做，期间所有检索和删除都要排队，一份大 PDF 就足以让线上全部问答卡住。现在是锁外算向量、锁内写入，并处理「算向量期间别处已创建索引」的竞态。

**写入失败要回滚**。落盘失败时如果只抛异常不回滚，会出现内存里有这份文档、磁盘没有、接口却返回 500 且上传文件已被删除，重启后文档凭空消失。现在失败时会弹出清单项并从索引删掉本次新增的片段。

**引用正则要覆盖模型的真实写法**。实测模型会写 `【E1】`、`[ E2 ]`、`[E1-E3]`，只认 `[E1]` 会把这些原样留在正文里，同时被判成「没有引用」。现在兼容全角括号、空格和范围写法，跨度超过 20 时只取两端。

**「未找到」必须是整段话术**。用 `in` 判断会让「公司成立于 1998 年。股东结构文档未找到」这类混着无引用结论的回答也通过校验，用户就看不到黄色提示。现在只有整段等于固定话术才算。

### 6. 运行日志如何服务评测

每个请求结束（成功或失败）都向 `AGENT_LOG_DIR/agent_runs.jsonl` 追加一行：

```json
{
  "ts": "2026-10-27T09:12:33+00:00",
  "question": "对比 A 和 B 的差异",
  "steps": [{"step": 1, "tool": "search_kb", "args": {"query": "A"}, "ok": true, "summary": "命中 5 条：…"}],
  "evidence_count": 5,
  "answer": "…[1][2]…",
  "grounded": true,
  "elapsed_ms": 8123
}
```

这份日志能直接支撑后续的离线评测：
- **检索质量**：`steps` 里的 query 和命中的文件名，用来判断该不该扩充知识库、关键词怎么改。
- **步数分布**：`steps` 长度告诉你模型平均几轮收敛，用来调 `AGENT_MAX_STEPS`。
- **幻觉率**：`grounded=false` 的比例就是无引用回答占比，可以作为回归指标；改动提示词后对比这个数就知道有没有变差。
- **失败归因**：带 `error` 字段的行单独统计，区分模型报错、工具异常和超时。

写日志失败只打 warning，不影响响应——日志是旁路，不能成为新的故障点。

## 测试

```bash
# 后端（假 Embedding / 假 LLM，不访问外网）
cd backend
pip install -r requirements-dev.txt
pytest -q

# 前端
cd frontend
npm run typecheck && npm run lint && npm test && npm run build
```

后端测试覆盖：路径穿越与上传校验、片段 ID、读取相邻片段、文档内检索、删除与重启后一致性、旧索引备份、Agent 的 11 个场景（多步检索、编造引用剔除、无引用、无证据、空知识库、参数错误、重复调用、最大步数、连续错误、SSE 接口、运行日志）。

前端测试覆盖：SSE 解析（分块、多事件、CRLF、心跳、非法 JSON）、错误转换（字符串 / 数组 / 无法解析）、转发层（目标 URL、请求头白名单、路径穿越、502、响应头清理）、ChatApp 交互（无文档禁用、时间线、流式替换、黄色提示、错误展示、快速问答）、输入法组字时不发送。

## CI/CD

```
push main / PR → main
    │
    ▼
backend-test（pytest） + frontend-test（typecheck / lint / test / build）
    │  PR 只跑到这里
    ▼
build-and-push（matrix：ai-kb-qa 从 ./backend，ai-kb-qa-web 从 ./frontend）
    │  标签：latest + commit sha
    ▼
deploy（rollout restart；ai-kb-qa-web 不存在时跳过，不让 job 失败）
```

## 云部署（Sealos）

- 后端镜像 `ghcr.io/995113756yong-create/ai-kb-qa:latest`，容器端口 8000，需要环境变量 `OPENAI_API_KEY` 和 `AGENT_MODEL`，并给 `/app/backend/uploads`、`/app/backend/faiss_index` 挂载持久卷
- 前端镜像 `ghcr.io/995113756yong-create/ai-kb-qa-web:latest`，容器端口 3000，开启公网访问，环境变量 `BACKEND_URL=http://ai-kb-qa:8000`（以 Sealos 控制台显示的内网地址为准）

## License

MIT
