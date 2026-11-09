"""多专家 Agent 存储：每个专家一份人设 + 一个完全独立的知识库。

设计取舍：
- agents.json 单文件清单 + 每专家一个目录（uploads/ faiss_index/ logs/）。
  不引入数据库：单人使用的规模下 JSON 足够，且目录即备份，拷走即迁移。
- default 专家指向旧版 backend/uploads + backend/faiss_index，
  已有部署、评测脚本（eval/ 打默认接口）、MCP Server 全都不用改。
- default 专家不可删除（内置兜底），其余专家可增可删。
"""
import json
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.document import KnowledgeBase
from app.i18n import tr
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

AGENTS_FILE = "agents.json"
MANIFEST_VERSION = 1
AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
MODEL_RE = re.compile(r"^[\w./:-]{1,100}$")
DEFAULT_AGENT_ID = "default"
VALID_ANSWER_MODES = ("strict", "reference")

# 内置默认专家：不落盘（agents.json 里不存它），永远存在
DEFAULT_AGENT = {
    "agent_id": DEFAULT_AGENT_ID,
    "name": "通用助手",
    "description": "基于上传文档回答任意领域的问题",
    "persona": "",
    "greeting": "",
    "emoji": "🤖",
    "model": "",
    "created_at": "",
    "builtin": True,
}

MAX_NAME_LEN = 40


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AgentStore:
    """进程内单例：持有全部专家定义与各自的 KnowledgeBase 缓存。"""

    def __init__(
        self,
        store_dir: str,
        default_upload_dir: str,
        default_index_dir: str,
        default_log_dir: str,
        embeddings: Embeddings,
    ):
        self.store_dir = store_dir
        self.default_upload_dir = default_upload_dir
        self.default_index_dir = default_index_dir
        self.default_log_dir = default_log_dir
        self.embeddings = embeddings
        self._lock = threading.Lock()
        self._agents: Dict[str, dict] = {}
        self._kbs: Dict[str, KnowledgeBase] = {}
        self._load()

    # ---------- 持久化 ----------

    def _manifest_path(self) -> str:
        return os.path.join(self.store_dir, AGENTS_FILE)

    def _load(self) -> None:
        path = self._manifest_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("专家清单读取失败（%s），按空清单启动", e)
            return
        agents = data.get("agents", []) if isinstance(data, dict) else []
        for entry in agents:
            agent_id = entry.get("agent_id") if isinstance(entry, dict) else None
            if isinstance(agent_id, str) and AGENT_ID_RE.fullmatch(agent_id):
                self._agents[agent_id] = entry

    def _save(self) -> None:
        """在锁内调用：原子写清单。"""
        os.makedirs(self.store_dir, exist_ok=True)
        tmp = self._manifest_path() + ".tmp"
        payload = {"version": MANIFEST_VERSION, "agents": list(self._agents.values())}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._manifest_path())

    # ---------- 目录布局 ----------

    def _agent_dir(self, agent_id: str) -> str:
        return os.path.join(self.store_dir, agent_id)

    def upload_dir_of(self, agent_id: str) -> str:
        if agent_id == DEFAULT_AGENT_ID:
            return self.default_upload_dir
        return os.path.join(self._agent_dir(agent_id), "uploads")

    def index_dir_of(self, agent_id: str) -> str:
        if agent_id == DEFAULT_AGENT_ID:
            return self.default_index_dir
        return os.path.join(self._agent_dir(agent_id), "faiss_index")

    def log_dir_of(self, agent_id: str) -> str:
        if agent_id == DEFAULT_AGENT_ID:
            return self.default_log_dir
        return os.path.join(self._agent_dir(agent_id), "logs")

    # ---------- 读写 ----------

    def get(self, agent_id: str) -> Optional[dict]:
        """返回专家定义的拷贝；default 未自定义时返回内置定义。"""
        if agent_id == DEFAULT_AGENT_ID:
            with self._lock:
                stored = self._agents.get(DEFAULT_AGENT_ID)
            entry = dict(stored or DEFAULT_AGENT)
            entry.setdefault("starter_questions", [])
            return entry
        with self._lock:
            entry = self._agents.get(agent_id)
        return dict(entry) if entry else None

    def list_agents(self) -> List[dict]:
        """default 永远排第一，其余按创建顺序。answer_mode 统一补全供前端显示。"""
        with self._lock:
            others = [dict(e) for e in self._agents.values() if e.get("agent_id") != DEFAULT_AGENT_ID]
        head = self.get(DEFAULT_AGENT_ID)
        head["answer_mode"] = effective_mode(head)
        head.setdefault("starter_questions", [])
        for e in others:
            e.setdefault("answer_mode", "reference")
            e.setdefault("starter_questions", [])
        return [head] + others

    def create(
        self,
        name: str,
        description: str = "",
        persona: str = "",
        greeting: str = "",
        emoji: str = "",
        model: str = "",
        agent_id: Optional[str] = None,
        answer_mode: str = "reference",
        starter_questions: Optional[list] = None,
    ) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError(tr("agent.name_required"))
        if len(name) > MAX_NAME_LEN:
            raise ValueError(tr("agent.name_too_long", max_len=MAX_NAME_LEN))
        model = (model or "").strip()
        if model and not MODEL_RE.fullmatch(model):
            raise ValueError(tr("agent.model_invalid"))
        answer_mode = (answer_mode or "reference").strip()
        if answer_mode not in VALID_ANSWER_MODES:
            raise ValueError(tr("agent.answer_mode_invalid", modes=VALID_ANSWER_MODES))
        starters = [str(q).strip() for q in (starter_questions or []) if str(q).strip()]
        if len(starters) > 4:
            raise ValueError(tr("agent.starters_too_many"))

        if agent_id is None:
            agent_id = uuid.uuid4().hex[:8]
        agent_id = agent_id.strip().lower()
        if not AGENT_ID_RE.fullmatch(agent_id):
            raise ValueError(tr("agent.id_invalid"))
        if agent_id == DEFAULT_AGENT_ID:
            raise ValueError(tr("agent.id_reserved"))
        if self.get(agent_id) is not None:
            raise ValueError(tr("agent.id_exists", agent_id=agent_id))

        entry = {
            "agent_id": agent_id,
            "name": name,
            "description": (description or "").strip(),
            "persona": (persona or "").strip(),
            "greeting": (greeting or "").strip(),
            "emoji": (emoji or "").strip(),
            "model": model,
            "answer_mode": answer_mode,
            "starter_questions": starters,
            "created_at": now_iso(),
            "builtin": False,
        }

        # 目录先建好，清单最后写：清单里有的专家一定有目录
        os.makedirs(self.upload_dir_of(agent_id), exist_ok=True)
        os.makedirs(os.path.dirname(self.index_dir_of(agent_id)), exist_ok=True)

        with self._lock:
            # 锁内再查一次：上面那次检查在锁外，两个请求同时用同一个 ID 创建时
            # 都能通过，后写入的会覆盖前一个。
            if agent_id in self._agents:
                raise ValueError(tr("agent.id_exists", agent_id=agent_id))
            self._agents[agent_id] = entry
            self._save()
        return dict(entry)

    def save_agent(self, entry: dict) -> Optional[dict]:
        """更新单个专家的清单记录（用于字段迁移）。专家不存在时忽略。"""
        agent_id = entry.get("agent_id")
        with self._lock:
            if agent_id not in self._agents:
                return None
            self._agents[agent_id] = dict(entry)
            self._save()
        return dict(entry)

    def delete(self, agent_id: str) -> Optional[dict]:
        """删除专家及其全部数据（文档、索引、日志）。default 不可删，返回 None。"""
        if agent_id == DEFAULT_AGENT_ID:
            return None
        with self._lock:
            entry = self._agents.pop(agent_id, None)
            if entry is not None:
                self._save()
        if entry is None:
            return None
        with self._lock:
            self._kbs.pop(agent_id, None)
        shutil.rmtree(self._agent_dir(agent_id), ignore_errors=True)
        return entry

    # ---------- 知识库 ----------

    def kb(self, agent_id: str) -> KnowledgeBase:
        """每个专家一个 KnowledgeBase，构造后缓存复用。"""
        if self.get(agent_id) is None:
            raise KeyError(tr("agent.not_found_id", agent_id=agent_id))
        with self._lock:
            kb = self._kbs.get(agent_id)
        if kb is not None:
            return kb
        kb = KnowledgeBase(self.index_dir_of(agent_id), self.embeddings)
        with self._lock:
            # 并发时可能别的线程已建好，沿用先建的那个
            existing = self._kbs.setdefault(agent_id, kb)
        return existing


def effective_mode(entry: dict) -> str:
    """专家的有效回答模式。

    default 专家 -> DEFAULT_AGENT_ANSWER_MODE（strict）；
    其他专家 -> entry.get("answer_mode") or "reference"
    （旧 agents.json 记录没有该字段，按 reference 处理，线上行为不变）。
    """
    from app import config

    if not entry or entry.get("agent_id") == DEFAULT_AGENT_ID:
        mode = config.DEFAULT_AGENT_ANSWER_MODE
        return mode if mode in VALID_ANSWER_MODES else "strict"
    mode = entry.get("answer_mode")
    return mode if mode in VALID_ANSWER_MODES else "reference"
