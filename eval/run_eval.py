"""评测脚本：双模式评测 + LLM-as-judge + 阈值校准。

用法：
    # 用假实现跑（不花钱、不联网，验证脚本本身）
    python -m eval.run_eval --mock --mode both --judge
    python -m eval.calibrate_threshold --mock

    # 打真实接口跑（需要 OPENAI_API_KEY，会产生费用）
    python -m eval.run_eval --base http://localhost:8000 --mode both --judge --admin-token <口令> --out eval/report.md
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import mean, quantiles

EVAL_DIR = Path(__file__).resolve().parent
CASES_FILE = EVAL_DIR / "cases.jsonl"
RESULTS_DIR = EVAL_DIR / "results"

NOT_FOUND_ANSWER = "文档中未找到相关信息。"

# 模式：默认两种都跑；用例可用 modes 字段覆盖
DEFAULT_MODES = ["strict", "reference"]

# reference 模式下拒答判定的宽松匹配（开头声明来源即可）
REJECT_DECLAIM_RE = re.compile(r"(知识库|文档)中?(暂无|没有|未找到)")

# 20 条内置离题负例（阈值校准用）
OFFTOPIC = [
    "明天会下雨吗",
    "如何学习 Rust 的所有权",
    "推荐几部科幻电影",
    "怎么做红烧肉",
    "光速是多少",
    "Python 和 Go 选哪个",
    "怎么写辞职信",
    "秦始皇统一六国是哪一年",
    "火星上有生命吗",
    "怎么办理护照",
    "量子计算机会取代经典计算机吗",
    "全球变暖的主要原因",
    "怎么挑笔记本电脑",
    "为什么要学英语",
    "宇宙的年龄是多少",
    "怎么做拿铁咖啡",
    "红楼梦的作者是谁",
    "怎么缓解焦虑",
    "区块链是什么",
    "怎么选枕头",
]


# ---------- 结果收集 ----------


class CaseResult:
    def __init__(self, case: dict, mode: str):
        self.case = case
        self.mode = mode
        self.answer = ""
        self.sources: list[dict] = []
        self.grounded = True
        self.steps = 0
        self.elapsed_ms = 0
        self.error = ""
        self.grounded_ratio = None
        self.segments: list[dict] = []
        self.numeric_warnings = 0
        self.usage: dict = {}
        self.faithfulness = None
        # 逐项判定
        self.retrieval_hit = False
        self.answer_hit = False
        self.reject_correct = False
        self.citation_ok = False
        self.ratio_ok = True
        self.numeric_ok = True

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        return (
            self.retrieval_hit
            and self.answer_hit
            and self.citation_ok
            and self.ratio_ok
            and self.numeric_ok
        )

    def to_raw(self) -> dict:
        return {
            "id": self.case["id"],
            "mode": self.mode,
            "question": self.case["question"],
            "category": self.case["category"],
            "agent": self.case.get("agent", "default"),
            "answer": self.answer,
            "sources": [
                {k: s.get(k) for k in ("index", "source", "page")}
                for s in self.sources
            ],
            "grounded": self.grounded,
            "grounded_ratio": self.grounded_ratio,
            "numeric_warnings": self.numeric_warnings,
            "usage": self.usage,
            "faithfulness": self.faithfulness,
            "passed": self.passed,
            "error": self.error,
        }


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
    if case["category"] == "reject":
        return True
    expect = case.get("expect_sources") or []
    min_sources = case.get("expect_min_sources")
    got_files = {s.get("source") for s in result.sources if s.get("source")}
    if expect:
        return any(f in got_files for f in expect)
    if min_sources:
        return len(got_files) >= min_sources
    # reference 模式的 mixed 用例：半可答也算检索命中（比例另有判定）
    return len(got_files) > 0


def judge_answer(case: dict, result: CaseResult) -> bool:
    if case["category"] == "reject":
        # 分模式判定：
        # strict: 恰好输出固定话术
        # reference: sources 为空 + 比例为 0/None + 开头声明来源
        if result.mode == "strict":
            return result.answer.strip() == NOT_FOUND_ANSWER
        if result.sources:
            return False
        if result.grounded_ratio not in (0, None):
            return False
        return bool(REJECT_DECLAIM_RE.search(result.answer[:120]))

    keywords = case.get("expect_keywords") or []
    by_mode = case.get("expect_keywords_by_mode") or {}
    if result.mode in by_mode:
        keywords = by_mode[result.mode]
    keyword_hit = any(k in result.answer for k in keywords)
    # mixed 类：strict 模式除了关键词，还要求明确说明「未找到」的部分
    if case["category"] == "mixed" and result.mode == "strict":
        return keyword_hit and "未找到" in result.answer
    if not keywords:
        return result.answer.strip() != "" and result.answer.strip() != NOT_FOUND_ANSWER
    return keyword_hit


def judge_citation(case: dict, result: CaseResult) -> bool:
    if case["category"] == "reject":
        return True
    cited = {int(m) for m in re.findall(r"\[(\d+)\]", result.answer)}
    available = {s["index"] for s in result.sources}
    if not cited:
        return not result.grounded or result.answer.strip() == NOT_FOUND_ANSWER
    return cited <= available


def judge_ratio(case: dict, result: CaseResult) -> bool:
    expect = case.get("expect_ratio") or {}
    rng = expect.get(result.mode)
    if not rng:
        return True
    ratio = result.grounded_ratio
    if ratio is None:
        # 全 neutral / 全 kb 拒答：mixed 类在 reference 模式不该出现
        return False
    return rng[0] <= ratio <= rng[1]


def judge_numeric(case: dict, result: CaseResult) -> bool:
    if case.get("allow_numeric_warnings"):
        return True
    return result.numeric_warnings == 0


def _judge(case: dict, r: CaseResult) -> None:
    r.retrieval_hit = judge_retrieval(case, r)
    r.answer_hit = judge_answer(case, r)
    r.reject_correct = judge_answer(case, r)
    r.citation_ok = judge_citation(case, r)
    r.ratio_ok = judge_ratio(case, r)
    r.numeric_ok = judge_numeric(case, r)


# ---------- 指标汇总 ----------


def summarize(results: list[CaseResult]) -> dict:
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.case["category"], []).append(r)

    def rate(items, attr):
        if not items:
            return 0.0
        return sum(1 for i in items if getattr(i, attr)) / len(items)

    ratios = [r.grounded_ratio for r in results if r.grounded_ratio is not None]
    # 数字一致率：没有警告的 kb 句 / kb 句总数（across cases）
    kb_total = 0
    kb_clean = 0
    for r in results:
        for seg in r.segments:
            if seg.get("kind") == "kb":
                kb_total += 1
                if not seg.get("warnings"):
                    kb_clean += 1

    elapsed = sorted(r.elapsed_ms for r in results)

    def pctile(seq, p):
        if not seq:
            return 0
        idx = min(int(len(seq) * p), len(seq) - 1)
        return seq[idx]

    usage = [r.usage for r in results if r.usage]
    tokens = [
        u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usage
    ]
    faith = [r.faithfulness for r in results if r.faithfulness is not None]

    import os

    price_in = float(os.getenv("PRICE_INPUT_PER_M", "0") or 0)
    price_out = float(os.getenv("PRICE_OUTPUT_PER_M", "0") or 0)

    return {
        "total": len(results),
        "errors": sum(1 for r in results if r.error),
        "retrieval_rate": rate(results, "retrieval_hit"),
        "answer_rate": rate(results, "answer_hit"),
        "citation_rate": rate(results, "citation_ok"),
        "reject_rate": rate(by_cat.get("reject", []), "reject_correct"),
        "pass_rate": rate(results, "passed"),
        "avg_ratio": mean(ratios) if ratios else None,
        "numeric_consistency": kb_clean / kb_total if kb_total else None,
        "faithfulness": mean(faith) if faith else None,
        "latency_p50": pctile(elapsed, 0.5),
        "latency_p95": pctile(elapsed, 0.95),
        "avg_tokens": mean(tokens) if tokens else 0,
        "price_in": price_in,
        "price_out": price_out,
        "by_category": {
            cat: {"n": len(items), "pass_rate": rate(items, "passed")}
            for cat, items in sorted(by_cat.items())
        },
    }


def format_report(all_summaries: dict, all_results: dict, title: str) -> str:
    def pct(x):
        return f"{x * 100:.1f}%" if x is not None else "—"

    lines = [f"# {title}", ""]

    for mode, summary in all_summaries.items():
        results = all_results[mode]
        lines += [
            f"## {mode} 模式（{summary['total']} 例，错误 {summary['errors']}）",
            "",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
            f"| 整体通过率 | **{pct(summary['pass_rate'])}** | 5 项判定全部通过 |",
            f"| 检索命中率 | {pct(summary['retrieval_rate'])} | 期望文档出现在 sources |",
            f"| 回答命中率 | {pct(summary['answer_rate'])} | 关键词命中或拒答判定正确 |",
            f"| 引用合法率 | {pct(summary['citation_rate'])} | 每个 [n] 对应到 sources |",
            f"| 拒答/声明正确率 | {pct(summary['reject_rate'])} | 按模式判定 |",
            f"| 平均知识库依据比例 | {pct(summary['avg_ratio'])} | grounded_ratio 均值 |",
            f"| 数字一致率 | {pct(summary['numeric_consistency'])} | 无警告 kb 句 / kb 句总数 |",
            f"| 忠实度（judge） | {pct(summary['faithfulness'])} | LLM 评判 kb 句被证据支持比例 |",
            f"| 延迟 P50 / P95 | {summary['latency_p50'] / 1000:.1f}s / {summary['latency_p95'] / 1000:.1f}s | |",
            f"| 平均 token / 题 | {summary['avg_tokens']:.0f} | prompt + completion |",
        ]
        if summary["price_in"] > 0 and summary["avg_tokens"] > 0:
            cost = summary["avg_tokens"] * 0.5 / 1e6 * summary["price_in"] + summary["avg_tokens"] * 0.5 / 1e6 * summary["price_out"]
            lines.append(f"| 估算费用 / 题 | ¥{cost:.4f} | 按 token 对半估算 |")
        else:
            lines.append("| 估算费用 / 题 | 未配置 | 设 PRICE_INPUT_PER_M / PRICE_OUTPUT_PER_M |")
        lines.append("")

        lines += [
            "### 分类通过率",
            "",
            "| 分类 | 用例数 | 通过率 |",
            "|------|--------|--------|",
        ]
        for cat, info in summary["by_category"].items():
            lines.append(f"| {cat} | {info['n']} | {pct(info['pass_rate'])} |")
        lines.append("")

    # 失败用例汇总
    failed = [r for mode in all_results for r in all_results[mode] if not r.passed]
    if failed:
        lines += ["## 未通过用例", ""]
        for r in failed:
            marks = []
            if not r.retrieval_hit:
                marks.append("检索未命中")
            if not r.answer_hit:
                marks.append("回答未命中")
            if not r.citation_ok:
                marks.append("引用有问题")
            if not r.ratio_ok:
                marks.append("依据比例不达标")
            if not r.numeric_ok:
                marks.append(f"数字警告 {r.numeric_warnings} 处")
            if r.error:
                marks.append(f"错误: {r.error}")
            ans = r.answer.replace("\n", " ")[:80]
            lines.append(f"- **{r.case['id']}**（{r.mode}）`{r.case['question'][:40]}`")
            lines.append(f"  - 问题：{'、'.join(marks)}")
            lines.append(f"  - 实际回答：{ans}")
        lines.append("")

    return "\n".join(lines)


# ---------- 执行器 ----------


def run_remote(base, cases, mode, upload, admin_token=""):
    """打真实接口，跑指定模式的用例。upload 只重灌 default 专家语料。"""
    base = base.rstrip("/")

    def api(path, payload=None, method="GET", timeout=120, headers=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            base + path,
            data=data,
            headers={"Content-Type": "application/json", **(headers or {})},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}

    admin_headers = {"X-Admin-Token": admin_token} if admin_token else {}

    if upload:
        for doc in api("/api/docs")["docs"]:
            api(f"/api/docs/{doc['doc_id']}", method="DELETE", headers=admin_headers)
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
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    **admin_headers,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
        print("已重灌 default 语料")

    results: list[CaseResult] = []
    todo = [c for c in cases if mode in c.get("modes", DEFAULT_MODES)]
    for i, case in enumerate(todo, 1):
        r = CaseResult(case, mode)
        t0 = time.time()
        try:
            req = urllib.request.Request(
                base + "/api/agent/stream",
                data=json.dumps(
                    {
                        "question": case["question"],
                        "agent_id": case.get("agent", "default"),
                        "answer_mode": mode,
                    },
                    ensure_ascii=False,
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
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
                        r.grounded_ratio = ev.get("grounded_ratio")
                        r.segments = ev.get("segments") or []
                        r.usage = ev.get("usage") or {}
                        r.numeric_warnings = sum(
                            len(s.get("warnings", [])) for s in r.segments
                        )
                    elif ev.get("type") == "error":
                        r.error = ev["detail"]
        except urllib.error.HTTPError as e:
            r.error = f"HTTP {e.code}"
        except Exception as e:
            r.error = f"{type(e).__name__}: {e}"
        r.elapsed_ms = int((time.time() - t0) * 1000)

        _judge(case, r)
        mark = "OK  " if r.passed else "FAIL"
        print(f"  [{i:>2}/{len(todo)}] {mark} {case['id']:<4} {mode:<9} {case['question'][:30]}")
        results.append(r)
    return results


def run_mock(cases, mode):
    """不联网的假执行器，覆盖脚本全部分支；指标不可信。"""
    from eval.judge import JudgeClient

    mock_judge = JudgeClient(mock=True)

    def mock_verdict(seg):
        v = mock_judge.complete("evidence", "statement")
        return 1.0 if v and v.get("supported") else 0.0

    results = []
    todo = [c for c in cases if mode in c.get("modes", DEFAULT_MODES)]
    for case in todo:
        r = CaseResult(case, mode)
        cat = case["category"]
        if cat == "reject":
            if mode == "strict":
                r.answer = NOT_FOUND_ANSWER
            else:
                r.answer = "知识库中暂无相关资料，以下回答基于一般知识，仅供参考。\n\n这个我知识库里没有。"
            r.segments = []
            r.grounded_ratio = 0 if mode == "reference" else None
        else:
            # mock 回答：一半 kb 一半 general，让 ratio/segments/usage 都有值
            kws = case.get("expect_keywords") or ["答案"]
            kb_text = f"关键数字 {kws[0]} [1]"
            gen_text = "补充说明这一句是一般知识。"
            if cat == "precise":
                kb_text = f"配置号命中 {kws[0]} [1]"
            r.answer = f"{kb_text}\n{gen_text}"
            r.sources = [
                {
                    "index": 1,
                    "source": (case.get("expect_sources") or ["产品A.txt"])[0],
                    "content": f"关键数字 {kws[0]}",
                }
            ]
            r.segments = [
                {"text": kb_text, "kind": "kb", "citations": [1], "warnings": []},
                {"text": gen_text + "\n", "kind": "general", "citations": [], "warnings": []},
            ]
            r.grounded_ratio = 0.5
            r.usage = {"prompt_tokens": 1000, "completion_tokens": 200, "llm_calls": 3}
            # 数字检查分支：allow_numeric_warnings 用例造一个警告
            if case.get("allow_numeric_warnings"):
                r.segments[0]["warnings"] = ["数字 123 未出现在引用片段中，可能是推算或编造"]
                r.numeric_warnings = 1
        r.grounded = cat != "reject" or mode == "strict"
        r.steps = 2
        r.elapsed_ms = 1500
        _judge(case, r)
        results.append(r)
    return results


def check_fitness_ready(base):
    """有健身用例时先确认语料已播种；没播种就跳过这些用例并警告。"""
    try:
        req = urllib.request.Request(
            base.rstrip("/") + "/api/docs?agent_id=fitness-coach", method="GET"
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            docs = json.loads(r.read().decode()).get("docs", [])
        return bool(docs)
    except Exception:
        return False


# ---------- 入口 ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="双模式评测")
    parser.add_argument("--base", help="后端地址，如 http://localhost:8000")
    parser.add_argument("--mock", action="store_true", help="用假实现，不联网")
    parser.add_argument("--mode", choices=["strict", "reference", "both"], default="both")
    parser.add_argument("--agent", help="只跑指定专家的用例")
    parser.add_argument("--judge", action="store_true", help="开启 LLM-as-judge 忠实度评判")
    parser.add_argument("--admin-token", default="", help="重灌语料的管理员口令")
    parser.add_argument("--no-upload", action="store_true", help="跳过清空+上传语料")
    parser.add_argument("--raw-dir", default=str(RESULTS_DIR), help="原始结果目录")
    parser.add_argument("--out", help="报告输出路径")
    parser.add_argument("--title", default="Agent 评测报告")
    args = parser.parse_args()

    if not args.base and not args.mock:
        print("必须指定 --base 或 --mock")
        return 2

    cases = load_cases(CASES_FILE)
    if args.agent:
        cases = [c for c in cases if c.get("agent", "default") == args.agent]
    modes = (
        DEFAULT_MODES
        if args.mode == "both"
        else [args.mode]
    )
    print(f"加载 {len(cases)} 个用例，模式：{modes}\n")

    all_results: dict[str, list[CaseResult]] = {}
    for mode in modes:
        if args.mock:
            all_results[mode] = run_mock(cases, mode)
        else:
            # 健身语料就绪检查
            fitness_cases = [c for c in cases if c.get("agent") == "fitness-coach"]
            if fitness_cases and not check_fitness_ready(args.base):
                print(f"[警告] 健身专家语料未播种，跳过 {len(fitness_cases)} 条健身用例")
                cases = [c for c in cases if c.get("agent") != "fitness-coach"]
            upload = (not args.no_upload) and mode == modes[0]
            all_results[mode] = run_remote(
                args.base, cases, mode, upload=upload, admin_token=args.admin_token
            )

    # LLM-as-judge
    if args.judge:
        from eval.judge import JudgeClient, faithfulness, judge_segments

        client = JudgeClient(mock=args.mock)
        for mode, results in all_results.items():
            for r in results:
                if not r.segments or r.error:
                    continue
                verdicts = judge_segments(r.segments, r.sources, r.case["question"], client)
                supported = sum(
                    1 for _, v in verdicts if v and v.get("supported")
                )
                total = sum(1 for _, v in verdicts if v is not None)
                r.faithfulness = supported / total if total else None
            print(f"[judge] {mode} 完成")

    all_summaries = {m: summarize(rs) for m, rs in all_results.items()}
    report = format_report(all_summaries, all_results, args.title)

    # 原始结果落盘（一行一条 JSON）
    if not args.mock:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        raw_dir = Path(args.raw_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        for mode, results in all_results.items():
            path = raw_dir / f"{stamp}-{mode}.jsonl"
            path.write_text(
                "\n".join(json.dumps(r.to_raw(), ensure_ascii=False) for r in results) + "\n",
                encoding="utf-8",
            )
            print(f"原始结果已写入 {path}")

    print()
    print(report)

    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\n报告已写入 {args.out}")

    return 0 if all(s["errors"] == 0 for s in all_summaries.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
