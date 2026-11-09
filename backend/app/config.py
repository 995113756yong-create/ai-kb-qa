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

# 规则意图识别：进入 ReAct 循环前先用规则分流。
# 闲聊直接回复、列文档直接调工具，都不走带工具的 LLM 决策；
# 带编号实体或明说"文档里"的问题先用原问题检索一次；其余交给模型判断。
INTENT_ROUTING_ENABLED = os.getenv("INTENT_ROUTING_ENABLED", "true").lower() == "true"

# 多专家存储根目录：每个自定义专家一个子目录（uploads/faiss_index/logs）。
# default 专家不进来，沿用上面的 UPLOAD_DIR / FAISS_DIR / AGENT_LOG_DIR。
AGENTS_DIR = os.getenv("AGENTS_DIR", os.path.join(BACKEND_DIR, "agents_store"))


AGENT_LOG_DIR = os.getenv("AGENT_LOG_DIR", os.path.join(BACKEND_DIR, "logs"))

# ============ 可信回答与评测体系（feat/trust-and-eval） ============

# 证据门槛：余弦相似度低于该值、且没有命中编号关键词的片段，不登记为证据。
# 真实 Embedding 校准值（eval/calibrate_threshold.py）：正例保留 95.8% / 负例拦截 95.8%。
EVIDENCE_MIN_SIM = float(os.getenv("EVIDENCE_MIN_SIM", "0.46"))

# 默认专家（通用文档问答）的回答模式。
# strict：只答知识库，无依据时输出固定话术拒答；
# reference：知识库优先 + 通用知识兜底，并做句子级来源标注。
DEFAULT_AGENT_ANSWER_MODE = os.getenv("DEFAULT_AGENT_ANSWER_MODE", "strict")

# 管理员口令：设置后，建/删专家、上传、删文档都必须带 X-Admin-Token 请求头；
# 为空时不校验（仅限本地开发）。
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# 问答限流：每个客户端每分钟最多请求数，0 表示关闭。
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))

# 是否信任 X-Forwarded-For。经 Next.js 转发部署时必须设为 true，
# 否则所有用户共用一个限流桶。
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

# 流式回答时是否向模型服务请求 usage 统计。
# 如果服务不支持 stream_options 导致流式请求报错，设为 false（回答阶段用量记 0）。
LLM_STREAM_USAGE = os.getenv("LLM_STREAM_USAGE", "true").lower() == "true"

# LLM-as-judge 评测模型（建议与生成模型不同，减少自我偏好）
JUDGE_MODEL = os.getenv("JUDGE_MODEL") or os.getenv("AGENT_MODEL")
JUDGE_API_BASE = os.getenv("JUDGE_API_BASE") or OPENAI_API_BASE
JUDGE_API_KEY = os.getenv("JUDGE_API_KEY") or OPENAI_API_KEY

# 评测费用估算（元 / 百万 token），用于报告；不配则显示"未配置"
PRICE_INPUT_PER_M = float(os.getenv("PRICE_INPUT_PER_M", "0") or 0)
PRICE_OUTPUT_PER_M = float(os.getenv("PRICE_OUTPUT_PER_M", "0") or 0)

# 模型调用超时（秒）。流式回答时是两个 chunk 之间的读超时，不是整段回答的总时长。
# 不设上限时 SDK 默认 600 秒，模型服务一卡就会长时间占住后台线程。
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
# 模型调用失败重试次数上限（SDK 默认 2，模型服务抖动时容易叠加成长时间等待）
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
# Embedding 调用超时（秒）
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))

# 反馈文件大小上限（MB）。/api/feedback 不需要鉴权、每条最大约 9.5KB，
# 不设上限会无限增长；超过后轮转为 feedback.jsonl.1，磁盘最多占用约 2 倍上限。
FEEDBACK_MAX_MB = float(os.getenv("FEEDBACK_MAX_MB", "5"))

# 多轮追问改写：有历史且问题像追问时，先把它改写成可独立检索的问题
CONTEXTUALIZE_ENABLED = os.getenv("CONTEXTUALIZE_ENABLED", "true").lower() == "true"
# 送进改写 prompt 的历史轮数上限（一问一答算一轮）
CONTEXTUALIZE_MAX_TURNS = int(os.getenv("CONTEXTUALIZE_MAX_TURNS", "3"))

# 文档原文接口的返回上限（字符）。超出时只返回前若干页并置 truncated=true。
DOC_CONTENT_MAX_CHARS = int(os.getenv("DOC_CONTENT_MAX_CHARS", "500000"))
