"""证据登记表与引用校验：模型只引用短编号，由程序负责把编号映射回真实片段。"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document

from app.qa import NOT_FOUND_ANSWER, SNIPPET_LEN

# 模型写出的引用形如 [E3]，也可能一行里写多个，如 [E1, E3] / [E1、E3]；
# 只认登记过的编号，未登记的编号会被剔除
CITATION_GROUP_RE = re.compile(r"\[([Ee]\d+(?:\s*[,，、]\s*[Ee]\d+)*)\]")
CITATION_ID_RE = re.compile(r"[Ee](\d+)")


@dataclass
class Evidence:
    """一条登记过的证据，编号形如 E1。"""

    evidence_id: str
    document: Document
    metadata: Dict[str, str] = field(default_factory=dict)


def _chunk_key(doc: Document) -> str:
    """同一片段重复出现时沿用原编号，用 chunk_id 作为去重键。"""
    metadata = doc.metadata or {}
    chunk_id = metadata.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    return f"{metadata.get('doc_id')}:{metadata.get('chunk_index')}"


class EvidenceRegistry:
    """一次对话请求一个实例，负责分配编号、去重和最终引用校验。"""

    def __init__(self) -> None:
        self._by_key: Dict[str, Evidence] = {}
        self._order: List[str] = []

    def register(self, doc: Document) -> Evidence:
        key = _chunk_key(doc)
        existing = self._by_key.get(key)
        if existing is not None:
            return existing

        evidence = Evidence(evidence_id=f"E{len(self._order) + 1}", document=doc)
        self._by_key[key] = evidence
        self._order.append(key)
        return evidence

    def register_many(self, docs: List[Document]) -> List[Evidence]:
        return [self.register(doc) for doc in docs]

    def get(self, evidence_id: str) -> Optional[Evidence]:
        for key in self._order:
            evidence = self._by_key[key]
            if evidence.evidence_id == evidence_id:
                return evidence
        return None

    def is_empty(self) -> bool:
        return not self._order

    def __len__(self) -> int:
        return len(self._order)

    def all(self) -> List[Evidence]:
        return [self._by_key[key] for key in self._order]

    def format_for_prompt(self) -> str:
        """把登记过的证据拼成提示词片段，供回答阶段使用。"""
        blocks = []
        for evidence in self.all():
            meta = evidence.document.metadata or {}
            source = meta.get("source") or "未知文档"
            page = meta.get("page")
            location = f"{source} 第{page}页" if page else source
            blocks.append(
                f"[{evidence.evidence_id}] 来源：{location}\n{evidence.document.page_content}"
            )
        return "\n\n".join(blocks)

    def finalize(self, answer_text: str) -> Tuple[str, List[dict], bool]:
        """清洗回答中的引用并生成 sources。

        - 丢掉登记表里不存在的编号（模型编造的引用）；
        - 有效编号按首次出现顺序重编为 [1]、[2]……，一个括号内的多个编号合并成 [1][2]；
        - 完全没有有效引用且不是“未找到”类回答时，grounded=False。
        """
        # 先扫一遍确定使用顺序，再据此重编，保证编号与 sources 顺序一致
        used: List[str] = []
        for group in CITATION_GROUP_RE.finditer(answer_text):
            for number in CITATION_ID_RE.findall(group.group(1)):
                evidence_id = f"E{number}"
                if evidence_id not in used and self.get(evidence_id) is not None:
                    used.append(evidence_id)

        index_of = {evidence_id: i for i, evidence_id in enumerate(used, start=1)}

        def _replace(match: "re.Match[str]") -> str:
            numbers = CITATION_ID_RE.findall(match.group(1))
            # 编造的编号直接删掉，避免在正文里留下无法跳转的标记
            mapped = [index_of[f"E{n}"] for n in numbers if f"E{n}" in index_of]
            if not mapped:
                return ""
            # 去重保序，[E1, E1] 只保留一次
            unique = list(dict.fromkeys(mapped))
            return "".join(f"[{i}]" for i in unique)

        clean = CITATION_GROUP_RE.sub(_replace, answer_text).strip()
        sources = [self._to_source(evidence_id, index_of[evidence_id]) for evidence_id in used]

        grounded = bool(used) or _is_not_found(clean)
        return clean, sources, grounded

    def _to_source(self, evidence_id: str, index: int) -> dict:
        evidence = self.get(evidence_id)
        meta = evidence.document.metadata or {}
        return {
            "index": index,
            "doc_id": meta.get("doc_id"),
            "source": meta.get("source"),
            "page": meta.get("page"),
            "snippet": evidence.document.page_content[:SNIPPET_LEN],
        }


def _is_not_found(answer: str) -> bool:
    """“未找到”类回答本身不需要引用，也算 grounded。"""
    if not answer:
        return False
    return NOT_FOUND_ANSWER in answer or "未找到" in answer
