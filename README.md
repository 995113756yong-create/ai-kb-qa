# AI 知识库问答系统（RAG + 手写 ReAct Agent）

上传文档后自动切分、向量化，再基于文档内容回答问题。系统提供两条问答路径：**固定 RAG**（一次检索）作为对照基线，**手写 ReAct Agent**（多步检索 + 证据引用 + 流式输出）作为主路径。

支持**多专家模式**：可以创建任意领域的专家（每个专家有独立知识库 + 独立人设），内置一个开箱即用的「健身教练」专家作为示范。

**在线演示**：https://ldflnavviuft.cloud.sealos.io

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
  ├─ Agent     /api/agent/stream 规则意图分流 → 手写 ReAct 循环 → SSE 事件流
  │     ├─ 意图分流：闲聊直接回复 / 列文档直接调工具 / 编号类问题先预检索 / 其余交给模型
  │     ├─ 研究阶段：模型决定调用 search_kb / read_chunk / list_documents
  │     └─ 回答阶段：只带已登记的证据，流式生成 + 引用校验
  ├─ 多专家    /api/agents  AgentStore：每专家独立知识库/人设/日志
  │     └─ default 专家沿用旧目录，已有部署零迁移
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
| 关键词检索 | 自实现 BM25（无额外依赖） |
| 检索融合 | 归一化加权 + max 合并 |
| 工具协议 | 自实现 MCP Server（JSON-RPC 2.0 over stdio） |
| Embedding | BAAI/bge-large-zh-v1.5（硅基流动） |
| 对话模型 | `Qwen/Qwen2.5-7B-Instruct`（固定 RAG）/ `deepseek-ai/DeepSeek-V4.1-Flash`（Agent） |
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
- **混合检索**：向量 + BM25 关键词检索融合，解决配置号/型号等精确标识符的召回短板（见「混合检索」一节）
- **问答界面**：品牌色渐变 + 思考中动态指示 + 消息进场动效，深浅色自适应
- **多专家平台**：自建任意领域专家（独立知识库 + 人设 + 欢迎语 + 回答模式），内置健身教练专家与 4 份健身语料；知识库按专家完全隔离
- **两种回答模式**：严格模式只答知识库、无依据时输出固定话术拒答；参考模式知识库优先 + 通用知识兜底，并做句子级来源标注（按专家配置）
- **句子级溯源**：程序（而非模型自述）把回答拆句标注为「知识库 / 一般知识 / 中性」，前端用底色区分并显示「知识库依据 N%」
- **数字一致性检查**：引用句中的数字必须出现在引用片段里，否则红波浪标注（低成本确定性防幻觉）
- **证据门槛**：检索结果按绝对余弦相似度过滤，编号类查询保留关键词通道
- **写接口鉴权与限流**：ADMIN_TOKEN 保护写接口；问答按客户端限流

## 项目结构

```
ai-kb-qa/
├── backend/
│   ├── app/
│   │   ├── config.py           # 环境配置
│   │   ├── document.py         # 加载、切分、KnowledgeBase（FAISS + BM25 混合检索）
│   │   ├── retrieval.py        # BM25 + 向量融合（归一化加权 + max 合并）
│   │   ├── qa.py               # 固定 RAG 链与 QAService
│   │   ├── mcp_server.py       # MCP Server（JSON-RPC 2.0 over stdio）
│   │   ├── agent_store.py      # 多专家存储（每专家独立知识库）
│   │   ├── seed_agents.py      # 内置专家播种（健身教练 + 语料）
│   │   ├── main.py             # 应用工厂 create_app + 全部 HTTP 接口
│   │   └── agent/
│   │       ├── llm.py          # AgentLLM 协议 + OpenAI 兼容实现
│   │       ├── tools.py        # 工具定义（JSON Schema）与执行
│   │       ├── evidence.py     # 证据登记表与引用校验
│   │       ├── query_rewrite.py # 复合问题拆解（默认关闭）
│   │       ├── rerank.py       # LLM 二次排序（默认关闭）
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
├── eval/                       # 评测集：端到端 + 检索层隔离测试
│   ├── cases.jsonl
│   ├── retrieval_probes.jsonl
│   ├── corpus.py
│   ├── run_eval.py
│   └── bench_retrieval.py
├── docker-compose.yml          # 本地构建
├── docker-compose.prod.yml     # 拉取 GHCR 现成镜像
├── .github/workflows/docker-publish.yml
└── README.md
```

## 本地开发

### 方式一：docker compose（一条命令，推荐演示用）

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 API Key

docker compose up --build
# 浏览器访问 http://localhost:3000
```

两个服务分别是 `backend`（FastAPI，端口 8000）和 `frontend`（Next.js，端口 3000）。
`frontend` 通过 `BACKEND_URL=http://backend:8000` 找到后端——容器间走 compose
内部网络，用服务名而不是 `localhost`。

`frontend` 的启动条件是 `depends_on: backend: condition: service_healthy`，
会等后端 `/api/health` 探活通过再起前端，避免前端先起来、第一次请求直接 502。

知识库数据（上传文件、FAISS 索引、Agent 运行日志）落在三个具名卷
（`backend_uploads` / `backend_index` / `backend_logs`），`docker compose down`
不加 `-v` 不会丢数据；要彻底清空重新演示用 `docker compose down -v`。

不想本地构建镜像、只想用 CI 已经推送的镜像时：

```bash
docker compose -f docker-compose.prod.yml up -d

> **生产环境必须**：设置 `ADMIN_TOKEN`（强随机串）和 `TRUST_PROXY=true`，
> 并建议关闭后端的公网域名、只让前端经内网访问后端。
> 否则攻击者可以直连后端绕过 Next.js 限流，或伪造 X-Forwarded-For 绕过限流桶。
```

参见下方"从 GHCR 拉镜像运行"一节。

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
| `AGENT_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash` | Agent 模型，必须支持 OpenAI 的 tools 调用 |
| `AGENT_MAX_STEPS` | `6` | 研究阶段最多调用几轮模型 |
| `AGENT_SEARCH_K` | `5` | `search_kb` 默认返回的片段数（`run_agent` 调用时会覆盖工具内的默认值） |
| `AGENT_LOG_DIR` | `backend/logs` | Agent 运行日志目录 |
| `HYBRID_SEARCH_ENABLED` | `true` | 混合检索（向量 + BM25）开关，见「混合检索」一节 |
| `HYBRID_VECTOR_WEIGHT` / `HYBRID_BM25_WEIGHT` | `1.0` / `3.0` | 两路融合权重 |
| `QUERY_DECOMPOSE_ENABLED` | `false` | 复合问题拆解开关，默认关闭，原因见「查询改写与 Rerank」一节 |
| `RERANK_ENABLED` | `false` | LLM 二次排序开关，默认关闭，原因见同上 |
| `EVIDENCE_MIN_SIM` | `0.45`（待校准） | 证据门槛：余弦相似度低于该值且无编号关键词命中的片段不登记为证据 |
| `DEFAULT_AGENT_ANSWER_MODE` | `strict` | 默认专家回答模式（strict / reference） |
| `ADMIN_TOKEN` | 空 | 管理员口令：设置后写接口需要 X-Admin-Token 头 |
| `RATE_LIMIT_PER_MIN` | `10` | 问答限流：每客户端每分钟请求数，0 关闭 |
| `TRUST_PROXY` | `false` | 是否信任 X-Forwarded-For（转发部署必须 true）。开启时取 XFF **最右侧**一项，左侧由客户端控制不可信 |
| `LLM_STREAM_USAGE` | `true` | 流式回答请求 usage 统计；不支持时设 false |
| `JUDGE_MODEL` / `JUDGE_API_BASE` / `JUDGE_API_KEY` | 复用 OPENAI_* | LLM-as-judge 评判模型（建议与生成模型不同） |
| `PRICE_INPUT_PER_M` / `PRICE_OUTPUT_PER_M` | 空 | 评测费用估算（元/百万 token） |
| `AGENTS_DIR` | `backend/agents_store` | 多专家存储根目录（每专家一个子目录） |
| `MAX_UPLOAD_MB` | `10` | 单文件上传上限 |
| `TOP_K` | `3` | 固定 RAG 的检索片段数 |
| `LLM_TIMEOUT_SECONDS` | `60` | 模型调用超时（秒）。流式回答是两 chunk 之间的读超时 |
| `LLM_MAX_RETRIES` | `1` | 模型 / Embedding 调用失败重试次数上限 |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | Embedding 调用超时（秒） |
| `FEEDBACK_MAX_MB` | `5` | 反馈文件上限（MB），超过后轮转为 `feedback.jsonl.1` |

### 前端 `frontend/.env`

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_URL` | `http://localhost:8000` | 转发层的后端地址，**运行时**读取，可在部署时切换 |
| `TRUSTED_PROXY_HOPS` | `1` | Next.js 前面会追加 XFF 的可信代理层数；限流只认右数第 N 项，左侧不可信 |

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/docs` | 已索引文档列表 |
| POST | `/api/upload` | 上传文档并追加到索引（multipart/form-data） |
| DELETE | `/api/docs/{doc_id}` | 删除文档（`doc_id` 必须是 32 位小写十六进制） |
| POST | `/api/ask` | 固定 RAG 问答 |
| POST | `/api/agent/stream` | Agent 问答，SSE 流式返回 |
| GET | `/api/agents` | 专家列表（default 永远第一） |
| POST | `/api/agents` | 新建专家（name 必填；人设/简介/emoji 可选） |
| DELETE | `/api/agents/{agent_id}` | 删除专家及其全部数据（default 不可删） |

`docs` / `upload` / `ask` / `agent/stream` 均支持 `?agent_id=` 参数路由到对应专家的知识库，不带参数即 default（旧调用零改动）。

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
| `intent` | `intent`（chat / list_docs / kb_query / uncertain）、`reason`（命中的规则） |
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

### 7. 规则意图分流：能用规则确定的，不交给模型判断

ReAct 循环里"要不要检索、先查什么"全靠模型决定，每个请求至少一次带工具的 LLM 调用。
但有不少请求的意图一眼就能确定，于是在进入循环前加了一层规则分流（`backend/app/agent/intent.py`）：

| 意图 | 命中规则 | 处理方式 | 大模型调用 |
|------|----------|----------|-----------|
| `chat` | 整句都是寒暄 / 致谢 / 身份询问（≤20 字） | 不带工具，一次流式回复 | 1 次（无工具决策） |
| `list_docs` | 问"知识库里有哪些文档" | 直接调 `list_documents`，模板拼回答 | 0 次 |
| `kb_query` | 含配置号 / 型号等编号实体，或明说"文档里/知识库中" | 先用原问题预检索一次，结果交给模型，再进 ReAct | 正常 |
| `uncertain` | 以上都没命中 | 原 ReAct 流程，模型自己决定 | 正常 |

设计取舍：

- **宁可漏判，不可误判**。误判成闲聊会让本该检索的问题被直接回答，所以闲聊必须"整句都是寒暄"，
  "你好，产品A多少钱"这种夹带真实问题的一律不算；单测里专门有一条用例跑完整个评测集，断言没有一条真实问题被判成闲聊。
- **编号类问题强制预检索**。配置号、型号这类专属信息模型不可能凭常识答对，不该让它"判断要不要查"；
  预检索的查询会记入去重表，模型原样再查时直接短路。
- **规则只做分流，不做回答**。`kb_query` 预检索后仍走 ReAct 和引用校验，规则不会绕过防幻觉机制。
- 分流结果通过 `intent` 事件下发，前端在 Agent 时间线里显示，同时写进运行日志，便于统计规则命中率、排查误判。
- 开关：`INTENT_ROUTING_ENABLED`（默认开启）。在 36 条评测用例上，6 条编号类问题命中 `kb_query`，其余 30 条交给模型，零误判为闲聊。

## 多专家平台

可以创建任意领域的专家：每个专家一份**人设**（决定怎么说话）+ 一个**完全独立的知识库**（决定能引用什么）。
内置「健身教练」专家作为完整示范，开箱即用。

### 数据模型

```
agents_store/
├── agents.json              # 专家清单（atomic write）
└── fitness-coach/
    ├── uploads/             # 该专家的上传文件
    ├── faiss_index/         # 该专家的 FAISS 索引
    ├── logs/                # 该专家的运行日志
    └── ...
```

- **default 专家不落 agents_store**：沿用 `backend/uploads` + `backend/faiss_index`，
  已有部署、评测脚本（eval/ 打默认接口）、MCP Server 零迁移。
- 删除专家 = 删清单 + 删目录（文档、索引、日志全清），default 不可删。
- 为什么不引入数据库：单人使用的规模下 JSON 清单足够，目录即备份，拷走即迁移。

### 隔离边界

每个专家的 KnowledgeBase 完全独立。实测验证：

```
问健身专家「产品A的月费」（该文档只在 default 库）
  → 模型换了 3 次关键词检索无果 → 正确拒答「文档中未找到相关信息。」
  → 没有串库
```

切换专家时前端清空消息：跨专家保留消息会让引用指向另一个库的文档，反而误导。

### 人设如何生效

`persona` 拼进 ReAct 研究阶段的 system prompt；检索工具、证据编号、引用校验
的行为完全不变——人设只改变「怎么说话」，不改变「能引用什么」。防幻觉的边界
（引用必须来自已登记证据）对每个专家一视同仁。

### 播种幂等

健身语料只在**首次启动且知识库为空**时装载（`.seed_done` 标记）。
用户删掉语料后重启服务，不会被自动塞回。

## 回答模式与句子级溯源

### 为什么用程序标注来源，而不是让模型自己说明

模型自我声明不可验证。程序按「有没有合法引用」切句分类，结果确定、可测试、
可度量，`grounded_ratio` 可以直接写进评测报告。

### 两种回答模式

| 模式 | 行为 | 适用 |
|------|------|------|
| strict | 只答知识库；无依据输出固定话术拒答 | 企业文档问答（默认专家） |
| reference | 知识库优先 + 通用知识兜底，句子级来源标注 | 咨询类场景（健身教练） |

按专家配置（`answer_mode` 字段），评测可经请求体 `answer_mode` 覆盖跑双模式对比。

### 切句与分类

```
一个 span = 非终止符 + （终止符串 + 紧跟的引用标记 | 换行 | 结尾）
英文句点 "." 不作为终止符（避免切开 2.5 这类小数）
引用标记跟着前一句走："每周 3 次。[1]下一句" → "每周 3 次。[1]" + "下一句"
```

| 分类 | 判定 |
|------|------|
| kb | 带合法引用编号（编号必须存在于 sources） |
| neutral | 短文本（<6 核心字符）/ 小标题 / 来源声明、安全提醒 |
| general | 其余有内容的句子 |

`grounded_ratio = kb / (kb + general)`，全 neutral 时为 None。

### 数字一致性检查

只检查 kb 句：句中数字必须出现在**它引用的那些片段**原文或问题里
（用户自己给的数字不算编造）。这样能发现「引用了 A 片段、数字却来自别处」
的错误引用。

已知边界：不识别中文数字（「三十次」不检查）；推算出的数字会被告警，
所以 prompt 要求推算写在不带引用的句子里——评测里的 `derived` 类用例
（如「我 30 岁，轻松跑心率区间」）允许警告，作为观察项。

## 证据门槛

### 为什么用绝对余弦而不用融合分

- FAISS 返回 L2 距离平方，量纲取决于向量是否归一化（不同 Embedding 不一致）
- 融合分是 min-max 归一化的**相对分**：同一批结果里最差总是 0、最好总是 1，
  没法用固定阈值判断「这条结果到底相不相关」

因此门槛基于**绝对余弦相似度**：从 FAISS 取回片段向量（`reconstruct`），
直接和查询向量算余弦，与归一化状态无关。

### 双通道

编号/型号类 token（`6145`、`GB1001`）在语义空间里没有信息量，余弦天然偏低，
但它们是强信号——命中即可绕过余弦门槛（`keyword_hit` 通道）。

### 校准

已用真实 Embedding（bge-large-zh-v1.5）校准：`EVIDENCE_MIN_SIM=0.46`。
校准时的分布（正例 = 探针+健身 fact 命中片段；负例 = reject 用例+20 条离题问题 top1）：

| 集合 | min | P10 | 中位数 | P90 | max |
|------|-----|-----|--------|-----|-----|
| 正例（24 条） | 0.43 | 0.44 | 0.61 | 0.66 | 0.78 |
| 负例（48 条） | 0.17 | 0.20 | 0.31 | 0.42 | 0.69 |

选 0.46：正例保留 95.8%，负例拦截 95.8%；仅靠关键词通道通过的正例 1 条（编号类探针）。
重新校准用真实 Embedding 跑：

```bash
python -m eval.calibrate_threshold
```

输出正例/负例分布和 0.30~0.80 的阈值扫描表，推荐「正例保留率 ≥ 95% 的前提下
负例拦截率最高」的值。跑完把推荐值写进 `config.py` 和 `.env.example`。

## 查询改写与 Rerank

两个可选的 Agent 增强特性，**默认关闭**，但保留完整实现与测试，可通过环境变量打开。

### 查询改写（复合问题拆解）

**问题**：系统提示词写了"涉及多个对象时分别检索"，但这只是建议，模型经常偷懒。
"产品A和产品B的月费分别是多少"这类问题，模型可能只查了产品A就作答。

**实现**（`app/agent/query_rewrite.py`）：
1. 启发式预判（`should_attempt_decompose`）：命中"分别/各自"等强信号词，
   或"并列连词 + 比较类线索词"组合，才判定为"看起来像复合问题"——避免对
   每个简单问题都多花一次 LLM 调用。
2. 命中后调用一次 LLM 把问题拆成互相独立的子问题（最多 4 个），每个子问题
   预先调用 `search_kb` 并把证据登记进 `EvidenceRegistry`，SSE 流里产出
   `decompose` 事件供前端展示拆解结果。
3. 任何环节失败（LLM 报错、JSON 解析失败、拆出 0 个子问题）都静默退化为
   原问题单独处理，不影响主流程。

### Rerank（LLM 二次排序）

**问题**：混合检索解决的是召回（能不能捞回来），不保证 Top-K 的排序精度。

**实现**（`app/agent/rerank.py`）：不引入 cross-encoder 依赖，复用已有的
Agent 模型做一次打分：把查询和候选片段列出来，让模型给每个片段打 0-10 分，
按分数重排。候选数 < 2 时跳过（没有排序意义）。任何解析失败都原样返回输入
顺序，绝不让 rerank 变成故障点。

### 为什么默认关闭

在 21 条端到端评测集上做了 A/B（只翻 `QUERY_DECOMPOSE_ENABLED` / `RERANK_ENABLED`
两个环境变量，其余完全一致）：

| 配置 | 整体通过率 | 平均耗时 |
|------|:---:|:---:|
| 关闭（默认） | 95.2% | 9.0s |
| 开启 | 95.2% | 25.4s |

两者在当前评测集上**通过率完全一致**（同一条 `m2` 用例失败，原因是关键词判定
过严，与是否拆解无关），开启后平均耗时却涨了近 3 倍。

**根因**：当前用的 `deepseek-ai/DeepSeek-V4.1-Flash` 工具调用能力本身就强，
ReAct 循环已经会自发分头检索（多步检索场景见「Agent 设计」第 2 节），这一步
在小样本评测集上基本是重复劳动，没有体现增量收益。

**什么时候值得打开**：换成工具调用能力更弱的模型、或真实问题分布里复合问题
占比显著更高、检索候选质量更参差时，这两个特性应该能体现价值——保留实现
和完整的单元测试（`test_query_rewrite.py` / `test_rerank.py` / 
`test_runner_enhancements.py`），复测验证即可按需打开。

## 模型选择

Agent 循环依赖模型的 function calling 能力，选型时实测过这几个（同一份工具定义、同一个提示词）：

| 模型 | 是否主动调工具 | 说明 |
|------|:---:|------|
| `deepseek-ai/DeepSeek-V4.1-Flash` | ✅ | 主动检索，参数合理，性价比高（当前默认） |
| `Qwen/Qwen3-32B` | ✅ | 正常发起调用 |
| `Qwen/Qwen2.5-72B-Instruct` | ⚠️ | 会反问用户而不检索，需更强提示词约束 |
| `Qwen/Qwen2.5-7B-Instruct` | ❌ | 工具调用不稳定，只适合固定 RAG |

换模型只需改 `AGENT_MODEL` 环境变量，代码不用动，因为 `agent/llm.py` 走的是标准 OpenAI 协议。

固定 RAG（`/api/ask`）不走工具调用，用 7B 就够，成本和延迟都更低。

## 部署踩坑

项目在 Sealos 上部署时踩过几个坑，记录下来避免重复踩：

**Sealos 的 Service 名 ≠ workload 名。** 内网地址形如 `http://ai-kb-qa-zmtnddmomzjs.ns-dcnh2ec4:8000`，其中 `ai-kb-qa-zmtnddmomzjs` 是 **Service** 名，Deployment/StatefulSet 的名字是 `ai-kb-qa`。`kubectl rollout restart` 要用后者。

**挂了持久卷的应用是 StatefulSet。** Sealos App Launchpad 对需要持久化的应用用 StatefulSet（Pod 名 `app-0`），无状态应用用 Deployment（Pod 名 `app-hash-xxxx`）。CI 里查目标时必须两种都查：

```bash
kubectl get statefulset -n "$ns"    # 后端（挂了 uploads / faiss_index）
kubectl get deployment  -n "$ns"    # 前端
```

**`kubectl cluster-info` 会因 RBAC 失败。** 它要读 `kube-system` 里的 Service，而 Sealos 的 ServiceAccount 只有自己 namespace 的权限，会报 `Forbidden`，容易被误判成「连不上集群」。连通性探测应改用：

```bash
kubectl get --raw /version                      # 只要 API 应答即可，无需业务权限
kubectl auth can-i list deployments -n "$ns"    # 再验证目标 namespace
```

**ServiceAccount 按 namespace 隔离。** 一份 kubeconfig 只能操作自己的 namespace。前后端在不同 workspace 时需要两份，分别配到 `SEALOS_KUBECONFIG` 和 `SEALOS_KUBECONFIG_WEB`。

**不要靠命名规则猜 workload 名。** `ai-kb-qa` 和 `ai-kb-qa-web` 前缀互相包含，`ai-kb-qa-web-xxx` 同时符合「ai-kb-qa + 随机后缀」和「ai-kb-qa-web + 随机后缀」两种解读，纯字符串规则无法区分。用仓库变量显式指定。

## 混合检索

> **勘误（重要）**：混合检索从本版本（PR #13）开始才真正作用于 Agent 主路径。
> 此前 `search_kb` 用的是 `kb.search_with_scores()`（纯向量），混合检索只在固定 RAG 的
> `kb.search()` 里生效；README 里的「精确编号 20/20 = 100%」是用 `bench_retrieval`
> （走 `search()`）测出来的，Agent 实际没有用到。本版本把所有路径统一到
> `KnowledgeBase.retrieve()`，评测测到的就是线上实际运行的代码。


### 为什么需要

纯向量检索靠语义相似度，对**精确标识符**天然失效——`配置 6145`、`GB1001` 这类 token
在嵌入空间里几乎没有语义信息，与周围几十个结构相同的编号等价。实测：

```
查询「配置 6202 执行时间」
  纯向量 Top-5  →  全部是 6045 / 6080 / 6124 这些相邻编号，目标片段不在其中
  BM25  Top-1   →  正好是 6202 那一条
```

### 实现

```
查询 ──┬─→ 向量检索 Top-10 ─┐
      │                    ├─→ 归一化 → 加权 → max 合并 → Top-K
      └─→ BM25  Top-10 ────┘
```

**分词**（`retrieval.py:tokenize`）：不引依赖，自己切。

- 英文/数字/型号整体保留：`GB1001`、`6145` 不被拆碎，这是精确命中的前提
- 中文切单字 + 双字：「推送任务」→ `推`/`送`/`任`/`务`/`推送`/`送任`/`任务`

**融合**（`fuse_scores`）：归一化后加权，同片段取 **max** 而非 sum。

> 为什么取 max 而不是相加：一个片段在两路都出现，不代表它比「一路强烈命中」更相关。
> 实测中向量路的噪声经常也在 BM25 路的中游，相加会把这些噪声顶到第一，
> 把真正的精确命中挤下去。取 max 后「BM25 第 1」不会再被「向量第 1 + BM25 第 5」反超。

**权重**：`HYBRID_BM25_WEIGHT=3.0` / `HYBRID_VECTOR_WEIGHT=1.0`。

### 效果（20 个探针，隔离测试）

| 方案 | 语义类 | 精确编号类 | 总计 |
|------|:------:|:---------:|-----:|
| 纯向量 | 4/4 | 14/16 | 18/20 = **90.0%** |
| 混合检索 | 4/4 | 16/16 | 20/20 = **100.0%** |

复现命令：

```bash
python -m eval.bench_retrieval
```

## 评测

同一批 36 条用例在两种回答模式下各跑一遍（`--mode both --judge`），完整报告见
`eval/report.md`。2026-11-03 真实评测（DeepSeek-V4.1-Flash + bge-large-zh-v1.5）：

| 指标 | strict | reference | 说明 |
|------|--------|-----------|------|
| 整体通过率 | **97.2%** | **86.1%** | 5 项判定全部通过 |
| 检索命中率 | 100% | 100% | 期望文档出现在 sources |
| 回答命中率 | 100% | 86.1% | 关键词命中或拒答判定正确 |
| 引用合法率 | 100% | 100% | 每个 [n] 对应到 sources |
| 拒答/声明正确率 | 100% | 37.5% | reference 下拒答要求开头声明来源 |
| 平均知识库依据比例 | 96.5% | 58.2% | grounded_ratio 均值 |
| 数字一致率 | 95.0% | 100% | 无警告 kb 句 / kb 句总数 |
| 忠实度（LLM judge） | 91.6% | 89.7% | kb 句被证据支持的比例 |
| 延迟 P50 / P95 | 16.2s / 44.9s | 19.0s / 77.6s | |

**两种模式的解读**：
- strict（企业文档问答定位）：除 1 条推算类数字警告外全绿，拒答全部精确。
- reference（咨询定位）：兜底回答带来覆盖率提升（multi_hop 100% vs strict 75%），
  但拒答正确率降到 37.5%——模型用一般知识回答时，来源声明措辞不统一，
  部分回答没在前 120 字内声明"知识库中没有"。这是**产品取舍的可度量代价**，
  也是 prompt 迭代的明确方向。

复现：

```bash
python -m eval.run_eval --base http://localhost:8000 --mode both --judge --admin-token <口令> --out eval/report.md
python -m eval.calibrate_threshold   # 阈值校准
```
## MCP 接入

### 为什么

工具层原本绑死在 `agent/tools.py`，只能本项目用。抽象成 MCP Server 后，
任何支持 MCP 的客户端（Claude Desktop、Cursor 等）都能直接接入这个知识库。

### 实现

`app/mcp_server.py`，**零新增依赖**——用标准库实现 JSON-RPC 2.0 over stdio。

只实现三个方法：

| 方法 | 作用 |
|------|------|
| `initialize` | 握手，返回协议版本与能力 |
| `tools/list` | 返回工具定义，**复用 `agent/tools.py` 的同一份 schema** |
| `tools/call` | 执行工具，结果包成 MCP 的 `content` 数组 |

### 启动

```bash
cd backend
python -m app.mcp_server
```

读取 `FAISS_DIR` 指向的知识库，通过 stdin/stdout 收发 JSON-RPC。
**stdout 只输出协议数据**，日志一律走 stderr，否则会破坏协议流。

### 客户端配置示例（Claude Desktop）

```json
{
  "mcpServers": {
    "kb-qa": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/path/to/ai-kb-qa/backend"
    }
  }
}
```

### 协议细节

- 通知（无 `id` 的消息）**永远不响应**，包括方法不存在的情况——这是 JSON-RPC 2.0 的硬要求
- 工具内部错误（参数不对、编号不存在）返回 `isError: true` + 文本说明，让调用方自行判断
- 协议层错误（方法不存在、缺必填参数）返回 JSON-RPC `error`，错误码遵循规范
- 解析失败的请求返回 `-32700`，且**不中断后续请求**

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
- **后端 Service 不要配置公网 Ingress**：只允许前端在集群内访问。后端限流依赖 `TRUST_PROXY=true` 取 XFF 判断客户端 IP，一旦后端可被公网直连，客户端就能自行伪造 X-Forwarded-For 绕过限流。本地 `docker-compose.prod.yml` 已把后端端口绑到 `127.0.0.1`。

### 从 GHCR 拉镜像运行（不本地构建）

CI 每次合入 main 都会把两个镜像推到 GHCR。不想等本地 `docker build`（前端多阶段构建约 2~3 分钟）时，直接拉现成镜像：

```bash
cp backend/.env.example backend/.env   # 填入 API Key
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
# 浏览器访问 http://localhost:3000
```

与 `docker-compose.yml` 的区别只有 `image:` 代替 `build:`，其余网络、健康检查、持久卷的设计完全一样。

## License

MIT
