import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 模型服务（默认硅基流动，兼容 OpenAI 协议）
# 兼容旧 README 中写的 SILICONFLOW_API_KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
CHAT_MODEL = os.getenv("CHAT_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# 存储目录
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BACKEND_DIR, "uploads"))
FAISS_DIR = os.getenv("FAISS_DIR", os.path.join(BACKEND_DIR, "faiss_index"))
FRONTEND_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "frontend"))

# 上传限制
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

# 检索与切分参数
TOP_K = int(os.getenv("TOP_K", "3"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
