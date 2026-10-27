# AI 知识库问答系统 (RAG)

基于 RAG（Retrieval-Augmented Generation）架构的智能知识库问答系统。用户上传文档后，系统自动切分、向量化存储，并基于文档内容回答用户提问。

**在线演示**：https://suinlwijcdst.cloud.sealos.io

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| RAG 框架 | LangChain |
| 向量数据库 | FAISS |
| Embedding 模型 | BAAI/bge-large-zh-v1.5（硅基流动 API） |
| 对话模型 | Qwen/Qwen2.5-7B-Instruct（硅基流动 API） |
| 前端 | 原生 HTML/CSS/JS（单文件，零依赖） |
| 容器化 | Docker + GitHub Actions CI/CD |
| 云部署 | Sealos Cloud |

## 核心功能

- **文档上传与索引**：支持 TXT / PDF / Markdown 格式，自动切分（chunk_size=500, overlap=50）并向量存储
- **多文档知识库**：多次上传会追加到同一索引，服务启动时加载一次并常驻内存
- **智能问答**：基于 FAISS 语义检索 Top-3 相关片段，结合 LLM 生成回答
- **回答带出处**：返回每个引用片段的文件名、页码和原文，文档中没有相关内容时明确回答“未找到”
- **安全加固**：上传文件由服务端重命名，限制类型（txt/md/pdf）和大小（默认 10MB），静态资源路由防路径穿越
- **实时 Web 界面**：上传文档 → 提问 → 获取回答，全流程可视化
- **单服务部署**：FastAPI 同时托管前端和 API，一个端口搞定
- **CI/CD 自动化**：GitHub Actions 自动构建镜像并推送至 GHCR，push 即部署

## 项目结构

```
ai-kb-qa/
├── backend/
│   ├── app/
│   │   ├── config.py      # 环境配置（从 .env 读取）
│   │   ├── document.py     # 文档加载、切分、FAISS 存储
│   │   ├── qa.py           # RAG 链构建与问答
│   │   └── main.py         # FastAPI 入口（API 路由 + 前端托管）
│   ├── tests/              # pytest 测试（假 Embedding / 假 LLM，不调用外部 API）
│   ├── uploads/            # 上传文件存储
│   ├── faiss_index/        # FAISS 向量索引 + docs.json 文档清单
│   ├── .env.example        # 环境变量模板
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   └── index.html          # 单文件聊天界面
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # GitHub Actions CI/CD
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── README.md
```

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/995113756yong-create/ai-kb-qa.git
cd ai-kb-qa

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 .env，填入你的硅基流动 API Key

# 3. 一键启动
docker-compose up -d

# 访问 http://localhost:8000
```

### 方式二：本地开发

```bash
# 1. 克隆项目
git clone https://github.com/995113756yong-create/ai-kb-qa.git
cd ai-kb-qa

# 2. 安装后端依赖
cd backend
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的硅基流动 API Key

# 4. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 `http://localhost:8000` 即可使用（前端+API 同一服务）。

### 方式三：云部署（Sealos）

镜像已发布至 GitHub Container Registry，可直接在 Sealos App Launchpad 部署：

- 镜像地址：`ghcr.io/995113756yong-create/ai-kb-qa:latest`
- 容器端口：`8000`
- 环境变量：`OPENAI_API_KEY` = 你的硅基流动 API Key（兼容旧名 `SILICONFLOW_API_KEY`）
- 持久化：建议给 `/app/backend/uploads` 和 `/app/backend/faiss_index` 挂载持久卷，否则 Pod 重启后知识库会清空

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | — | 必填，模型服务 API Key |
| `OPENAI_API_BASE` | `https://api.siliconflow.cn/v1` | OpenAI 兼容接口地址 |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh-v1.5` | 向量模型 |
| `CHAT_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 对话模型 |
| `MAX_UPLOAD_MB` | `10` | 单文件上传上限 |
| `TOP_K` | `3` | 检索片段数 |

## 运行测试

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/docs` | 已索引文档列表 |
| POST | `/api/upload` | 上传文档并追加到索引（multipart/form-data） |
| POST | `/api/ask` | 问答接口（JSON body: `{"question": "..."}`） |

`/api/ask` 返回示例：

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
| GET | `/` | 前端界面 |

## 工作流程

```
用户上传文档
    │
    ▼
文档加载 (TextLoader / PyPDFLoader)
    │
    ▼
文本切分 (RecursiveCharacterTextSplitter, chunk=500, overlap=50)
    │
    ▼
向量化存储 (bge-large-zh-v1.5 → FAISS)
    │
    ▼
用户提问 ──→ FAISS 语义检索 Top-3 ──→ 带编号的片段 + Prompt ──→ LLM 生成回答 + 出处
```

## CI/CD 流程

```
git push main
    │
    ▼
GitHub Actions 自动触发
    │
    ▼
pytest 测试（PR 只跑到这一步）
    │
    ▼
Docker 构建镜像（latest + commit sha 两个标签） → 推送至 GHCR (ghcr.io)
    │
    ▼
Sealos 拉取最新镜像 → 自动部署
```

## License

MIT
