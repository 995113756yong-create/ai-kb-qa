"""评测脚本：跑评测集，算各项指标，输出报告。

用法：
    # 用假实现跑（不花钱、不联网，验证脚本本身）
    python -m eval.run_eval --mock

    # 打真实接口跑（需要 OPENAI_API_KEY，会产生费用）
    python -m eval.run_eval --base http://localhost:8000

    # 输出 markdown 报告到文件
    python -m eval.run_eval --base http://localhost:8000 --out eval/report.md
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import mean

EVAL_DIR = Path(__file__).resolve().parent
CASES_FILE = EVAL_DIR / "cases.jsonl"

NOT_FOUND_ANSWER = "文档中未找到相关信息。"


# ---------- 结果收集 ----------


class CaseResult:
    def __init__(self, case: dict):
        self.case = case
        self.answer = ""
        self.sources: list[dict] = []
        self.grounded = True
        self.steps = 0
        self.elapsed_ms = 0
        self.error = ""
        # 逐项判定
        self.retrieval_hit = False
        self.answer_hit = False
        self.reject_correct = False
        self.citation_ok = False

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        return self.retrieval_hit and self.answer_hit and self.citation_ok


def load_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


# ---------- 判定逻辑 ----------


def judge_retrieval(case: dict, result: CaseResult) -> bool:
    """检索命中：期望的文档出现在 sources 里。

    拒答类用例不考察检索（本来就没有相关文档）。
    """
    if case["category"] == "reject":
        return True

    expect = case.get("expect_sources") or []
    min_sources = case.get("expect_min_sources")

    got_files = {s.get("source") for s in result.sources if s.get("source")}

    if expect:
        return any(f in got_files for f in expect)
    if min_sources:
        return len(got_files) >= min_sources
    # 精确匹配类用例没写 expect_sources，只要有出处就算命中
    return len(got_files) > 0


def judge_answer(case: dict, result: CaseResult) -> bool:
    """回答命中：关键词命中，或拒答类完全等于固定话术。"""
    if case["category"] == "reject":
        return result.answer.strip() == case["expect_answer"].strip()

    keywords = case.get("expect_keywords") or []
    if not keywords:
        # 没有关键词要求（精确匹配类），只要不是拒答就算答了
        return result.answer.strip() != NOT_FOUND_ANSWER and bool(result.answer.strip())
    return any(k in result.answer for k in keywords)


def judge_citation(case: dict, result: CaseResult) -> bool:
    """引用准确：回答里的每个 [n] 都能在 sources 里找到对应编号。

    没引用时看 grounded：grounded=False 是正确行为（程序识别出没有依据）。
    拒答类不需要引用。
    """
    if case["category"] == "reject":
        return True

    cited = {int(m) for m in re.findall(r"\[(\d+)\]", result.answer)}
    available = {s["index"] for s in result.sources}

    if not cited:
        # 没引用但也不是拒答，说明这轮没找到证据，grounded 应该为 False
        return not result.grounded or result.answer.strip() == NOT_FOUND_ANSWER

    return cited <= available


def judge_reject(case: dict, result: CaseResult) -> bool:
    if case["category"] != "reject":
        return True
    return result.answer.strip() == case["expect_answer"].strip()


# ---------- 指标汇总 ----------


def summarize(results: list[CaseResult]) -> dict:
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.case["category"], []).append(r)

    def rate(items, attr):
        if not items:
            return 0.0
        return sum(1 for i in items if getattr(i, attr)) / len(items)

    # 精确匹配类单独看：这类最能体现混合检索的价值
    precise = by_cat.get("precise", [])
    reject = by_cat.get("reject", [])

    return {
        "total": len(results),
        "errors": sum(1 for r in results if r.error),
        "retrieval_rate": rate(results, "retrieval_hit"),
        "answer_rate": rate(results, "answer_hit"),
        "citation_rate": rate(results, "citation_ok"),
        "pass_rate": rate(results, "passed"),
        # 精确编号类的检索命中率 —— 向量检索在这类上通常很差
        "precise_rate": rate(precise, "retrieval_hit"),
        # 拒答准确率 —— 衡量防幻觉
        "reject_rate": rate(reject, "reject_correct"),
        "avg_steps": mean([r.steps for r in results]) if results else 0,
        "avg_elapsed_s": mean([r.elapsed_ms for r in results]) / 1000 if results else 0,
        "by_category": {
            cat: {
                "n": len(items),
                "pass_rate": rate(items, "passed"),
            }
            for cat, items in sorted(by_cat.items())
        },
    }


def format_report(summary: dict, results: list[CaseResult], title: str) -> str:
    def pct(x: float) -> str:
        return f"{x * 100:.1f}%"

    lines = [
        f"# {title}",
        "",
        f"用例总数 **{summary['total']}**，执行错误 {summary['errors']} 个",
        "",
        "## 总体指标",
        "",
        "| 指标 | 数值 | 说明 |",
        "|------|------|------|",
        f"| 检索命中率 | {pct(summary['retrieval_rate'])} | 期望文档出现在 sources 中 |",
        f"| 回答命中率 | {pct(summary['answer_rate'])} | 回答包含期望要点 |",
        f"| 引用准确率 | {pct(summary['citation_rate'])} | 每个 [n] 都能对应到 sources |",
        f"| 拒答准确率 | {pct(summary['reject_rate'])} | 文档无答案时给出固定话术 |",
        f"| 精确编号命中 | {pct(summary['precise_rate'])} | 配置号/型号类检索，混合检索的重点改善项 |",
        f"| **整体通过率** | **{pct(summary['pass_rate'])}** | 三项判定全部通过 |",
        f"| 平均步数 | {summary['avg_steps']:.1f} | Agent 平均调用工具轮数 |",
        f"| 平均耗时 | {summary['avg_elapsed_s']:.1f}s | |",
        "",
        "## 分类通过率",
        "",
        "| 分类 | 用例数 | 通过率 |",
        "|------|--------|--------|",
    ]
    for cat, info in summary["by_category"].items():
        lines.append(f"| {cat} | {info['n']} | {pct(info['pass_rate'])} |")

    failed = [r for r in results if not r.passed]
    if failed:
        lines += ["", "## 未通过用例", ""]
        for r in failed:
            marks = []
            if not r.retrieval_hit:
                marks.append("检索未命中")
            if not r.answer_hit:
                marks.append("回答未命中")
            if not r.citation_ok:
                marks.append("引用有问题")
            if r.error:
                marks.append(f"错误: {r.error}")
            ans = r.answer.replace("\n", " ")[:80]
            lines.append(f"- **{r.case['id']}** `{r.case['question']}`")
            lines.append(f"  - 问题：{'、'.join(marks)}")
            lines.append(f"  - 实际回答：{ans}")
            if r.sources:
                lines.append(f"  - 出处：{[s.get('source') for s in r.sources]}")

    return "\n".join(lines)


# ---------- 两种执行器 ----------


def run_remote(base: str, cases: list[dict], upload: bool) -> list[CaseResult]:
    """打真实接口。upload=True 时先清空并上传固定语料。"""
    base = base.rstrip("/")

    def api(path, payload=None, method="GET", timeout=120):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}

    if upload:
        for doc in api("/api/docs")["docs"]:
            api(f"/api/docs/{doc['doc_id']}", method="DELETE")
        for name, text in __import__("eval.corpus", fromlist=["FILES"]).FILES.items():
            boundary = "----eval"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                f"{text}\r\n"
                f"--{boundary}--\r\n"
            ).encode()
            req = urllib.request.Request(
                base + "/api/upload",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
        print(f"已上传 {len(__import__('eval.corpus', fromlist=['FILES']).FILES)} 份语料")

    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        r = CaseResult(case)
        t0 = time.time()
        try:
            req = urllib.request.Request(
                base + "/api/agent/stream",
                data=json.dumps({"question": case["question"]}, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=240) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").rstrip("\n")
                    if not line.startswith("data: "):
                        continue
                    ev = json.loads(line[6:])
                    if ev.get("type") == "final":
                        r.answer = ev["answer"]
                        r.sources = ev["sources"]
                        r.grounded = ev["grounded"]
                        r.steps = ev["steps"]
                    elif ev.get("type") == "error":
                        r.error = ev["detail"]
        except urllib.error.HTTPError as e:
            r.error = f"HTTP {e.code}"
        except Exception as e:
            r.error = f"{type(e).__name__}: {e}"
        r.elapsed_ms = int((time.time() - t0) * 1000)

        _judge(case, r)
        mark = "OK  " if r.passed else "FAIL"
        print(f"  [{i:>2}/{len(cases)}] {mark} {case['id']:<4} {case['question'][:34]}")
        results.append(r)

    return results


def run_mock(cases: list[dict]) -> list[CaseResult]:
    """不联网的假执行器，用来验证评测脚本本身，指标不可信。"""
    results = []
    for case in cases:
        r = CaseResult(case)
        cat = case["category"]
        if cat == "reject":
            r.answer = case["expect_answer"]
        else:
            r.answer = "（mock）" + "、".join(case.get("expect_keywords") or ["答案"]) + " [1]"
            r.sources = [{"index": 1, "source": (case.get("expect_sources") or ["产品A.txt"])[0]}]
            r.grounded = True
        # mock 模式下精确匹配类故意判失败，模拟向量检索的真实短板
        if cat == "precise":
            r.sources = []
            r.answer = "文档中未找到相关信息。"
        r.steps = 2
        r.elapsed_ms = 1000
        _judge(case, r)
        results.append(r)
    return results


def _judge(case: dict, r: CaseResult) -> None:
    r.retrieval_hit = judge_retrieval(case, r)
    r.answer_hit = judge_answer(case, r)
    r.reject_correct = judge_reject(case, r)
    r.citation_ok = judge_citation(case, r)


# ---------- 入口 ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="跑 Agent 评测集")
    parser.add_argument("--base", help="后端地址，如 http://localhost:8000")
    parser.add_argument("--mock", action="store_true", help="用假实现，不联网")
    parser.add_argument("--no-upload", action="store_true", help="跳过清空+上传语料")
    parser.add_argument("--out", help="报告输出路径")
    parser.add_argument("--title", default="Agent 评测报告")
    args = parser.parse_args()

    if not args.base and not args.mock:
        print("必须指定 --base 或 --mock")
        return 2

    cases = load_cases(CASES_FILE)
    print(f"加载 {len(cases)} 个用例\n")

    if args.mock:
        results = run_mock(cases)
    else:
        results = run_remote(args.base, cases, upload=not args.no_upload)

    summary = summarize(results)
    report = format_report(summary, results, args.title)

    print()
    print(report)

    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\n报告已写入 {args.out}")

    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
