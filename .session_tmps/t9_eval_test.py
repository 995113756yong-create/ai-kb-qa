import io

p = "backend/tests/test_eval_judge.py"
t = io.open(p, encoding="utf-8").read()

anchor = "def test_mixed_strict_requires_not_found_mention():"
assert anchor in t

new_tests = '''def test_reject_reference_accepts_general_knowledge_declaration():
    """prompt 允许「以下为一般知识，非知识库内容」这种声明，评测口径要对齐."""
    ok = _result(
        REJECT_CASE, "reference",
        answer="以下为一般知识，非知识库内容。量子纠缠是一种量子力学现象……",
        sources=[], grounded_ratio=0,
    )
    assert judge_answer(REJECT_CASE, ok) is True


def test_reject_reference_accepts_absence_wording_variants():
    """「证据中未出现」「资料不包含」等措辞都要认."""
    for wording in [
        "知识库证据中未出现该产品的月费信息，以下回答基于一般知识。",
        "现有资料不包含这项配置，以下回答基于一般知识。",
        "文档里未提及该字段，以下回答基于一般知识。",
    ]:
        r = _result(REJECT_CASE, "reference", answer=wording, sources=[], grounded_ratio=0)
        assert judge_answer(REJECT_CASE, r) is True, f"未识别: {wording}"


'''

t = t.replace(anchor, new_tests + anchor, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("test_eval_judge.py updated")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")