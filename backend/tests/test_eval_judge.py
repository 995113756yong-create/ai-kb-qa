"""评测脚本与 judge 的冒烟/单元测试（不联网）。"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from eval.judge import JudgeClient, faithfulness, judge_segments  # noqa: E402
from eval.run_eval import (  # noqa: E402
    CaseResult,
    judge_answer,
    judge_citation,
    judge_numeric,
    judge_ratio,
    judge_retrieval,
    load_cases,
)


CASES = Path(__file__).resolve().parent.parent.parent / "eval" / "cases.jsonl"


# ---------- 用例格式 ----------


def test_cases_loadable_and_wellformed():
    cases = load_cases(CASES)
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "用例 id 重复"
    for c in cases:
        assert c["question"]
        assert c["category"] in (
            "fact", "compare", "precise", "reject", "multi_hop", "mixed", "derived", "persona"
        )
        if c["category"] == "reject":
            assert c.get("expect_answer")
        for f in ("expect_ratio", "expect_keywords_by_mode"):
            if c.get(f):
                assert isinstance(c[f], dict)


def test_fitness_cases_present():
    cases = load_cases(CASES)
    fit = [c for c in cases if c.get("agent") == "fitness-coach"]
    assert len(fit) == 13
    assert {c["id"] for c in cases} >= {"ft1", "fc1", "fm1", "fd1", "fx1", "fp1", "fr1", "fr2", "fr3"}
    mixed_default = [c for c in cases if c.get("id") in ("x1", "x2")]
    assert len(mixed_default) == 2
    assert all("expect_ratio" in c for c in mixed_default)


# ---------- 分模式判定 ----------


def _result(case, mode, **kw):
    r = CaseResult(case, mode)
    for k, v in kw.items():
        setattr(r, k, v)
    return r


REJECT_CASE = {
    "id": "r1", "category": "reject", "question": "q",
    "expect_answer": "文档中未找到相关信息。",
}


def test_reject_strict_requires_exact_answer():
    r = _result(REJECT_CASE, "strict", answer="文档中未找到相关信息。")
    assert judge_answer(REJECT_CASE, r) is True
    r2 = _result(REJECT_CASE, "strict", answer="知识库中没有找到，不过我可以告诉你……")
    assert judge_answer(REJECT_CASE, r2) is False


def test_reject_reference_requires_declaim_and_no_sources():
    ok = _result(
        REJECT_CASE, "reference",
        answer="知识库中暂无相关资料，以下回答基于一般知识。量子纠缠是……",
        sources=[], grounded_ratio=0,
    )
    assert judge_answer(REJECT_CASE, ok) is True
    bad1 = _result(REJECT_CASE, "reference", answer="随便说说", sources=[], grounded_ratio=0)
    assert judge_answer(REJECT_CASE, bad1) is False  # 没有来源声明
    bad2 = _result(
        REJECT_CASE, "reference",
        answer="知识库中暂无相关资料", sources=[{"index": 1}], grounded_ratio=1.0,
    )
    assert judge_answer(REJECT_CASE, bad2) is False  # 拒答不该有 sources


def test_mixed_strict_requires_not_found_mention():
    case = {"id": "x1", "category": "mixed", "question": "q", "expect_keywords": ["30"]}
    ok = _result(case, "strict", answer="产品A月费 30 元 [1]。其余部分文档中未找到相关信息。")
    assert judge_answer(case, ok) is True
    bad = _result(case, "strict", answer="产品A月费 30 元 [1]。计费模式有按月和按年。")
    assert judge_answer(case, bad) is False


def test_ratio_judgement():
    case = {"id": "x1", "category": "mixed", "question": "q",
            "expect_ratio": {"reference": [0.01, 0.99]}}
    ok = _result(case, "reference", grounded_ratio=0.5)
    assert judge_ratio(case, ok) is True
    low = _result(case, "reference", grounded_ratio=0.005)
    assert judge_ratio(case, low) is False
    none_ratio = _result(case, "reference", grounded_ratio=None)
    assert judge_ratio(case, none_ratio) is False
    # strict 模式没有配置区间 → 不检查
    strict = _result(case, "strict", grounded_ratio=None)
    assert judge_ratio(case, strict) is True


def test_numeric_judgement():
    case = {"id": "d", "category": "derived", "question": "q", "allow_numeric_warnings": True}
    r = _result(case, "reference", numeric_warnings=3)
    assert judge_numeric(case, r) is True
    case2 = {"id": "f", "category": "fact", "question": "q"}
    r2 = _result(case2, "reference", numeric_warnings=1)
    assert judge_numeric(case2, r2) is False


def test_retrieval_mixed_reference_counts_partial():
    case = {"id": "x1", "category": "mixed", "question": "q",
            "expect_sources": ["产品A.txt"]}
    r = _result(case, "reference", sources=[{"index": 1, "source": "产品A.txt"}])
    assert judge_retrieval(case, r) is True


def test_citation_reject_ok():
    r = _result(REJECT_CASE, "strict", answer="文档中未找到相关信息。")
    assert judge_citation(REJECT_CASE, r) is True


# ---------- judge ----------


class FakeJudgeClient(JudgeClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, evidence, statement):
        self.calls.append((evidence, statement))
        return self.responses.pop(0) if self.responses else None


def test_judge_segments_kb_only():
    segments = [
        {"text": "每周训练 3 次。[1]", "kind": "kb", "citations": [1], "warnings": []},
        {"text": "补充说明。\n", "kind": "general", "citations": [], "warnings": []},
    ]
    sources = [{"index": 1, "source": "a.txt", "content": "每周训练 3 次。"}]
    client = FakeJudgeClient([{"supported": True, "reason": "直接支持"}])
    verdicts = judge_segments(segments, sources, "每周练几次", client)
    assert len(verdicts) == 1  # 只评判 kb 句
    assert verdicts[0][1]["supported"] is True
    # 证据用的是片段全文
    assert "每周训练 3 次。" in client.calls[0][0]


def test_judge_none_not_counted():
    segments = [
        {"text": "A [1]", "kind": "kb", "citations": [1], "warnings": []},
        {"text": "B [1]", "kind": "kb", "citations": [1], "warnings": []},
    ]
    sources = [{"index": 1, "content": "原文"}]
    client = FakeJudgeClient([{"supported": True}, None])
    verdicts = judge_segments(segments, sources, "", client)
    # 一条支持、一条无法评判（None 不计入）
    assert faithfulness([verdicts]) == 1.0


def test_judge_weighted_average():
    v1 = [("s", {"supported": True}), ("s", {"supported": False})]
    v2 = [("s", {"supported": True})]
    # 加权: 2/3
    assert faithfulness([v1, v2]) == pytest.approx(2 / 3)


def test_judge_empty():
    assert faithfulness([]) is None
    assert faithfulness([[("s", None)]]) is None


# ---------- mock 全链路冒烟 ----------


def test_run_eval_mock_smoke(capsys):
    from eval.run_eval import main

    sys.argv = ["run_eval", "--mock", "--mode", "both", "--judge", "--title", "冒烟"]
    code = main()
    out = capsys.readouterr().out
    assert "strict 模式" in out
    assert "reference 模式" in out
    assert "忠实度" in out
    assert code in (0, 1)  # mock 数据允许有失败用例


def test_calibrate_mock_smoke(capsys):
    from eval.calibrate_threshold import main as cal_main

    sys.argv = ["calibrate", "--mock"]
    code = cal_main()
    out = capsys.readouterr().out
    assert "正例" in out and "负例" in out
    assert "推荐" in out or "没有满足" in out
    assert code == 0
