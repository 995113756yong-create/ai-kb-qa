"""证据登记表与引用校验：模型只引用短编号，由程序负责把编号映射回真实片段。"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document

from app.qa import NOT_FOUND_ANSWER, SNIPPET_LEN

# 范围引用最多展开这么多个编号，防止模型写出离谱的跨度
MAX_RANGE_SPAN = 20

# 模型写出的引用写法很杂，实测会用到：
#   [E3]  【E3】  [ E3 ]  [E1, E3]  [E1、E3]  [E1-E3]
# 只认登记过的编号，未登记的编号会被剔除
CITATION_GROUP_RE = re.compile(r"[\[【]\s*([Ee]\d+(?:\s*(?:[,，、\-–—~]\s*[Ee]?\d+)*)?)\s*[\]】]")
# 从括号内容里抽出所有数字，范围写法在展开时处理
CITATION_ID_RE = re.compile(r"[Ee]?(\d+)")


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
            for number in _expand_numbers(group.group(1)):
                evidence_id = f"E{number}"
                if evidence_id not in used and self.get(evidence_id) is not None:
                    used.append(evidence_id)

        index_of = {evidence_id: i for i, evidence_id in enumerate(used, start=1)}

        def _replace(match: "re.Match[str]") -> str:
            numbers = _expand_numbers(match.group(1))
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


def _expand_numbers(group: str) -> List[int]:
    """把括号里的内容展开成编号列表，支持 [E1]、[E1, E3]、[E1-E3]。

    范围写法只在两侧都是 E 前缀时展开，避免把 [1-3] 这类误判成引用。
    """
    numbers: List[int] = []
    for part in re.split(r"\s*[,，、]\s*", group.strip()):
        if not part:
            continue
        span = re.fullmatch(r"([Ee]\d+)\s*[-–—~]\s*([Ee]\d+)", part)
        if span:
            start, end = int(span.group(1)[1:]), int(span.group(2)[1:])
            # 反着写也认，但限制跨度，避免模型写出 [E1-E9999] 撑爆
            low, high = sorted((start, end))
            if high - low <= MAX_RANGE_SPAN:
                numbers.extend(range(low, high + 1))
            else:
                numbers.extend([start, end])
            continue
        found = CITATION_ID_RE.fullmatch(part.strip())
        if found:
            numbers.append(int(found.group(1)))
    return numbers


def _is_not_found(answer: str) -> bool:
    """整段回答就是固定话术时才认作「未找到」。

    不能用 `in` 判断：像「公司成立于 1998 年。股东结构文档未找到」这种
    混着无引用结论的回答也会被放行，用户就看不到黄色提示了。
    """
    normalized = re.sub(r"\s+", "", answer or "").strip("。.!！")
    return normalized == re.sub(r"\s+", "", NOT_FOUND_ANSWER).strip("。.!！")
