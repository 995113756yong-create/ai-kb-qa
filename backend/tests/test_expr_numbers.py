"""显式算式的结果放行, 单独出现的推算数字仍然报警.

注意引用写法: 这里用 [1] 而不是 [E1] -- classify_span 只认纯数字编号,
[E1] 会让整句被判成 general, 数字检查根本不执行.
"""
from app.agent.attribution import attribute


def _sources():
    return [
        {
            "index": 1,
            "source": "a.txt",
            "content": "最多 5 个成员, 超出按每人 10 元",
            "snippet": "最多 5 个成员, 超出按每人 10 元",
        }
    ]


def test_explicit_expression_result_is_allowed():
    """a、b 都来自证据 且 算对了, 结果 c 不报警."""
    att = attribute("额外费用为 5 × 10 = 50 元 [1]。", _sources(), "10 个人")
    assert att.kb_count == 1
    assert att.numeric_warnings == 0


def test_wrong_calculation_still_warns():
    """算式写错时结果仍要报警."""
    att = attribute("额外费用为 5 × 10 = 60 元 [1]。", _sources(), "10 个人")
    assert att.numeric_warnings == 1
    assert "60" in att.segments[0].warnings[0]


def test_bare_derived_number_still_warns():
    """没有算式支撑的推算数字仍然报警 (保持原行为)."""
    att = attribute("额外费用为 50 元 [1]。", _sources(), "10 个人")
    assert att.numeric_warnings == 1
    assert "50" in att.segments[0].warnings[0]


def test_chained_expression_supported():
    """连算: 前一个算式的结果可作为后一个的操作数."""
    sources = [
        {"index": 1, "source": "a.txt", "content": "3 和 4 和 2", "snippet": "3 和 4 和 2"}
    ]
    att = attribute("3 + 4 = 7, 7 × 2 = 14 [1]。", sources, "")
    assert att.numeric_warnings == 0
