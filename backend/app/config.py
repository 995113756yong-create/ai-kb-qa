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

# 上传限制
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

# 检索与切分参数
TOP_K = int(os.getenv("TOP_K", "3"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# Agent（手写 ReAct 循环）
# Agent 依赖 function calling：实测 DeepSeek-V4.1-Flash 与 Qwen3-32B 会主动检索，
# 7B 不稳定只用于固定 RAG。换模型改这个环境变量即可，代码无需改动。
AGENT_MODEL = os.getenv("AGENT_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash")
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "6"))
AGENT_SEARCH_K = int(os.getenv("AGENT_SEARCH_K", "5"))
# 混合检索：向量 + BM25 关键词，用 RRF 融合。
# 纯向量对「配置 6145」这类精确编号无效，BM25 补足这部分召回。
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
RRF_K = int(os.getenv("RRF_K", "60"))
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "1.0"))
HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", "3.0"))

# 查询改写：复合问题（如 A和B分别是多少）先拆成子问题各自检索，
# 避免模型偷懒只检索一次漏掉其中一个对象。
#
# 默认关闭：在 21 条评测集上实测，开启前后整体通过率都是 95.2%（同一道用例失败），
# 没有体现出可衡量的收益，却多花一次 LLM 调用、平均耗时从 9.0s 涨到 25.4s。
# 原因：当前用的 DeepSeek-V4.1-Flash 工具调用能力本身就强，ReAct 循环已经会
# 自发分头检索，这一步基本是重复劳动。保留实现与测试，作为可选特性，
# 换成能力更弱的模型或更复杂的真实问题分布时可以按需打开。
QUERY_DECOMPOSE_ENABLED = os.getenv("QUERY_DECOMPOSE_ENABLED", "false").lower() == "true"

# Rerank：对检索候选用 LLM 二次打分排序，不引入 cross-encoder 依赖。
#
# 默认关闭：同样在现有评测集上未观察到可衡量的提升，原因是混合检索命中率已经
# 较高、候选数较少时重排空间有限。保留实现与测试，作为可选特性。
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "false").lower() == "true"

AGENT_LOG_DIR = os.getenv("AGENT_LOG_DIR", os.path.join(BACKEND_DIR, "logs"))
