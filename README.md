---
title: AI KB QA System
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AI 知识库问答系统 (RAG)

基于 RAG（Retrieval-Augmented Generation）架构的智能知识库问答系统。用户上传文档后，系统自动切分、向量化存储，并基于文档内容回答用户提问。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| RAG 框架 | LangChain |
| 向量数据库 | FAISS |
| Embedding 模型 | BAAI/bge-large-zh-v1.5（硅基流动 API） |
| 对话模型 | Qwen/Qwen2.5-7B-Instruct（硅基流动 API） |
| 前端 | 原生 HTML/CSS/JS（单文件，零依赖） |
| 容器化 | Docker + docker-compose |

## 核心功能

- **文档上传与索引**：支持 TXT / PDF / Markdown 格式，自动切分（chunk_size=500, overlap=50）并向量存储
- **智能问答**：基于 FAISS 语义检索 Top-3 相关片段，结合 LLM 生成精准回答
- **实时 Web 界面**：上传文档 → 提问 → 获取回答，全流程可视化
- **单服务部署**：FastAPI 同时托管前端和 API，一个端口搞定

## 项目结构

```
ai-kb-qa/
├── backend/
│   ├── app/
│   │   ├── config.py      # 环境配置（从 .env 读取）
│   │   ├── document.py     # 文档加载、切分、FAISS 存储
│   │   ├── qa.py           # RAG 链构建与问答
│   │   └── main.py         # FastAPI 入口（API 路由 + 前端托管）
│   ├── uploads/            # 上传文件存储
│   ├── faiss_index/        # FAISS 向量索引
│   ├── .env.example        # 环境变量模板
│   └── requirements.txt
├── frontend/
│   └── index.html          # 单文件聊天界面
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

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/upload` | 上传文档并建立索引（multipart/form-data） |
| POST | `/api/ask` | 问答接口（JSON body: `{"question": "..."}`） |
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
用户提问 ──→ FAISS 语义检索 Top-3 ──→ 构建 Prompt ──→ LLM 生成回答
```

## License

MIT