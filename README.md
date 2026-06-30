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

## 核心功能

- **文档上传与索引**：支持 TXT / PDF / Markdown 格式，自动切分（chunk_size=500, overlap=50）并向量存储
- **智能问答**：基于 FAISS 语义检索 Top-3 相关片段，结合 LLM 生成精准回答
- **实时 Web 界面**：上传文档 → 提问 → 获取回答，全流程可视化

## 项目结构

```
ai-kb-qa/
├── backend/
│   ├── app/
│   │   ├── config.py      # 环境配置（从 .env 读取）
│   │   ├── document.py     # 文档加载、切分、FAISS 存储
│   │   ├── qa.py           # RAG 链构建与问答
│   │   └── main.py         # FastAPI 入口（路由 + CORS）
│   ├── uploads/            # 上传文件存储
│   ├── faiss_index/        # FAISS 向量索引
│   ├── .env                # 环境变量（不提交）
│   ├── .env.example        # 环境变量模板
│   └── requirements.txt
├── frontend/
│   └── index.html          # 单文件聊天界面
├── .gitignore
└── README.md
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd ai-kb-qa

# 安装后端依赖
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的硅基流动 API Key
```

### 3. 启动后端

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```bash
cd frontend
python -m http.server 3000
```

打开浏览器访问 `http://localhost:3000` 即可使用。

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/upload` | 上传文档并建立索引（multipart/form-data） |
| POST | `/ask` | 问答接口（JSON body: `{"question": "..."}`） |

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