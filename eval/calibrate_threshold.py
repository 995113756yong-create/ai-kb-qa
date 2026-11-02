"""阈值校准脚本：在真实 Embedding 上确定 EVIDENCE_MIN_SIM 的取值。

正例：检索探针 + 健身 fact 用例，取期望文档命中片段的 vector_sim 最大值。
负例：reject 用例 + 20 条内置离题问题，取 top1 的 vector_sim。
在 0.30~0.80 之间扫描阈值，推荐「正例保留率 >= 95% 的前提下负例拦截率最高」的值。

用法：
    python -m eval.calibrate_threshold            # 真实 Embedding（用户本地跑）
    python -m eval.calibrate_threshold --mock     # 假 Embedding，只验证脚本能跑通
"""
import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR.parent))
sys.path.insert(0, str(EVAL_DIR.parent / "backend"))

from eval.run_eval import OFFTOPIC, load_cases  # noqa: E402


def build_kb(tmp_path, embeddings, files):
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path), embeddings)
    for i, (name, text) in enumerate(files.items()):
        path = Path(tmp_path).parent / name
        path.write_text(text, encoding="utf-8")
        chunks = load_and_split(str(path), f"doc{i}", name)
        kb.add_document(f"doc{i}", name, len(text), chunks)
    return kb


def quantiles_of(values):
    if not values:
        return {"min": 0, "p10": 0, "median": 0, "p90": 0, "max": 0}
    import statistics

    s = sorted(values)
    n = len(s)
    return {
        "min": s[0],
        "p10": s[min(int(n * 0.1), n - 1)],
        "median": statistics.median(s),
        "p90": s[min(int(n * 0.9), n - 1)],
        "max": s[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="证据阈值校准")
    parser.add_argument("--mock", action="store_true", help="假 Embedding，只验证脚本")
    args = parser.parse_args()

    import tempfile

    tmp = Path(tempfile.mkdtemp())

    # Embedding：mock 用假实现
    if args.mock:
        from langchain_core.embeddings import DeterministicFakeEmbedding

        embeddings = DeterministicFakeEmbedding(size=32)
    else:
        sys.path.insert(0, str(EVAL_DIR.parent / "backend"))
        from app.document import get_embeddings

        embeddings = get_embeddings()

    # 两个知识库：评测语料 + 健身语料
    from eval.corpus import FILES

    from app import seed_agents

    kb_eval = build_kb(tmp / "idx-eval", embeddings, FILES)
    kb_fit = build_kb(tmp / "idx-fit", embeddings, dict(seed_agents.FITNESS_CORPUS))

    # ---- 正例 ----
    probes = []
    for line in (EVAL_DIR / "retrieval_probes.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            probes.append(json.loads(line))

    cases = load_cases(EVAL_DIR / "cases.jsonl")

    pos_eval = []
    for p in probes:
        kb = kb_eval
        hits = kb.retrieve(p["query"], k=5)
        if not hits:
            continue
        # 期望文档命中的片段里取最高相似度
        for h in hits:
            if (h.doc.metadata or {}).get("source") == p.get("expect_doc"):
                pos_eval.append(h.vector_sim)
                break

    pos_fit = []
    for case in cases:
        if case.get("agent") != "fitness-coach" or case.get("category") != "fact":
            continue
        expect = case.get("expect_sources") or []
        hits = kb_fit.retrieve(case["question"], k=5)
        if not hits:
            continue
        # fact 用例：任何命中片段的最高相似度都算正例
        pos_fit.append(max(h.vector_sim for h in hits))

    # 编号类探针的正例余弦天然低，靠关键词通道通过——记录这个数量
    ident_probes = [p for p in probes if any(c.isdigit() for c in p["query"])]
    pos_keyword_only = 0
    for p in ident_probes:
        hits = kb_eval.retrieve(p["query"], k=5)
        passed_kw = [h for h in hits if h.keyword_hit]
        passed_sim = [h for h in hits if h.vector_sim >= 0.45]
        if passed_kw and not passed_sim:
            pos_keyword_only += 1

    # ---- 负例 ----
    neg_eval = []
    for case in cases:
        if case.get("category") != "reject":
            continue
        kb = kb_fit if case.get("agent") == "fitness-coach" else kb_eval
        hits = kb.retrieve(case["question"], k=3)
        if hits:
            neg_eval.append(max(h.vector_sim for h in hits))

    for q in OFFTOPIC:
        for kb in (kb_eval, kb_fit):
            hits = kb.retrieve(q, k=3)
            if hits:
                neg_eval.append(max(h.vector_sim for h in hits))

    pos = pos_eval + pos_fit
    print(f"正例 {len(pos)} 条（评测 {len(pos_eval)} + 健身 {len(pos_fit)}）")
    print(f"负例 {len(neg_eval)} 条")
    print()
    print("正例分布:", json.dumps(quantiles_of(pos), indent=2))
    print("负例分布:", json.dumps(quantiles_of(neg_eval), indent=2))
    print()

    # ---- 阈值扫描 ----
    print("| 阈值 | 正例保留率 | 负例拦截率 |")
    print("|------|-----------|-----------|")
    best = None
    t = 0.30
    while t <= 0.8001:
        keep = sum(1 for v in pos if v >= t) / len(pos) if pos else 0
        block = sum(1 for v in neg_eval if v < t) / len(neg_eval) if neg_eval else 0
        print(f"| {t:.2f} | {keep * 100:.1f}% | {block * 100:.1f}% |")
        if keep >= 0.95:
            if best is None or block > best[1]:
                best = (round(t, 2), block)
        t += 0.01

    print()
    if best:
        print(f"推荐 EVIDENCE_MIN_SIM = {best[0]}（正例保留 >= 95%，负例拦截率 {best[1] * 100:.1f}%）")
    else:
        print("0.30~0.80 内没有满足正例保留率 >= 95% 的阈值，请检查分布")
    print(f"仅靠关键词门槛通过的正例数：{pos_keyword_only}（编号类探针）")
    print()
    print("用真实 Embedding 跑完后：把推荐值写入 backend/app/config.py 和 backend/.env.example，")
    print("分布表贴进 README 的「证据门槛」一节。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
