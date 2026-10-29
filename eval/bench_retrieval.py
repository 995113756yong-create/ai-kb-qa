"""检索层基准测试：对比纯向量 vs 混合检索的召回能力。

为什么要单独测：Agent 会多轮换关键词重试，把单次检索的短板掩盖掉。
要证明混合检索的价值，必须隔离「检索」这一个变量。

用法：
    python -m eval.bench_retrieval            # 真实 Embedding，对比两种方案
    python -m eval.bench_retrieval --mock     # 假 Embedding，只验证脚本
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from eval.corpus import FILES  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
PROBES_FILE = EVAL_DIR / "retrieval_probes.jsonl"


class Probe:
    def __init__(self, d: dict):
        self.query = d["query"]
        self.expect_doc = d["expect_doc"]
        self.expect_keyword = d.get("expect_keyword")
        self.any_doc = bool(d.get("any_doc"))
        self.note = d.get("note", "")


def load_probes() -> list:
    probes = []
    for line in PROBES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            probes.append(Probe(json.loads(line)))
    return probes


def build_kb(tmp_path, embeddings, hybrid: bool):
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path / ("idx-h" if hybrid else "idx-v")), embeddings)
    for i, (name, text) in enumerate(FILES.items()):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        chunks = load_and_split(str(path), "doc%d" % i, name)
        kb.add_document("doc%d" % i, name, len(text), chunks)
    kb.hybrid_enabled = hybrid
    return kb


def hit(probe: Probe, docs) -> bool:
    """命中判定。

    any_doc=True 时不限定文档（多个文档都含目标内容的情况），
    只要求结果里有片段包含期望关键词。
    """
    for d in docs:
        if not probe.any_doc and d.metadata.get("source") != probe.expect_doc:
            continue
        if probe.expect_keyword and probe.expect_keyword not in d.page_content:
            continue
        return True
    return False


def run(kb, probes, k: int, label: str) -> dict:
    rows = [hit(p, kb.search(p.query, k=k)) for p in probes]
    return {"label": label, "k": k, "rows": rows, "hit": sum(rows)}


def report(runs, probes) -> str:
    lines = ["# 检索层基准", ""]
    lines.append("探针 **%d** 个，语料 **%d** 份" % (len(probes), len(FILES)))
    lines.append("")
    lines.append("对比「纯向量检索」与「混合检索（向量 + BM25 + RRF）」在同一批探针上的召回表现。")
    lines.append("")
    lines.append("> 隔离测试：不走 Agent、不重试，只测一次 `search()` 的召回能力。")
    lines.append("> Agent 会多轮换关键词，会掩盖单次检索的短板，所以必须单独测这一层。")
    lines.append("")

    header = "| 探针 | 期望文档 | " + " | ".join(r["label"] for r in runs) + " |"
    sep = "|------|----------|" + "|".join([":---:"] * len(runs)) + "|"
    lines += [header, sep]

    for i, probe in enumerate(probes):
        marks = ["OK" if r["rows"][i] else "**MISS**" for r in runs]
        lines.append("| %s | %s | %s |" % (probe.query, probe.expect_doc, " | ".join(marks)))

    lines += ["", "## 汇总", "", "| 方案 | 命中 | 命中率 |", "|------|------|--------|"]
    for r in runs:
        total = len(r["rows"])
        rate = r["hit"] / total * 100 if total else 0
        lines.append("| %s (k=%d) | %d/%d | **%.1f%%** |" % (r["label"], r["k"], r["hit"], total, rate))

    # 精确编号类：带数字关键词的探针
    id_idx = [
        i
        for i, p in enumerate(probes)
        if p.expect_keyword and any(ch.isdigit() for ch in p.expect_keyword)
    ]
    if id_idx:
        lines += [
            "",
            "## 精确编号类探针（混合检索的重点收益）",
            "",
            "配置号、型号这类 token 在嵌入空间里没有语义信息，",
            "纯向量检索只能靠上下文猜，BM25 能精确命中。",
            "",
            "| 方案 | 命中 | 命中率 |",
            "|------|------|--------|",
        ]
        for r in runs:
            got = sum(1 for i in id_idx if r["rows"][i])
            rate = got / len(id_idx) * 100
            lines.append("| %s | %d/%d | **%.1f%%** |" % (r["label"], got, len(id_idx), rate))

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="确定性假 Embedding，不联网")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out")
    args = parser.parse_args()

    import tempfile

    if args.mock:
        from langchain_core.embeddings import DeterministicFakeEmbedding

        embeddings = DeterministicFakeEmbedding(size=64)
        print("使用确定性假 Embedding（指标不可信，仅验证脚本）")
    else:
        from app.document import get_embeddings

        embeddings = get_embeddings()
        print("使用真实 Embedding")

    probes = load_probes()
    tmp = Path(tempfile.mkdtemp())

    kb_vec = build_kb(tmp, embeddings, hybrid=False)
    total_chunks = kb_vec._store.index.ntotal
    print("语料 %d 份，切成 %d 片，探针 %d 个" % (len(FILES), total_chunks, len(probes)))
    print("k=%d，单次检索只能看到全库 %.1f%%\n" % (args.k, args.k / total_chunks * 100))

    runs = [
        run(kb_vec, probes, args.k, "纯向量"),
        run(build_kb(tmp, embeddings, hybrid=True), probes, args.k, "混合检索"),
    ]

    text_out = report(runs, probes)
    print(text_out)

    if args.out:
        Path(args.out).write_text(text_out + "\n", encoding="utf-8")
        print("\n已写入 %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
