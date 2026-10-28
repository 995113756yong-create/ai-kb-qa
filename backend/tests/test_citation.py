"""P0-2 引用校验的回归测试：多种写法识别、编造剔除、未找到判定收紧。"""
import pytest
from langchain_core.documents import Document

from app.agent.evidence import EvidenceRegistry, _expand_numbers, _is_not_found
from app.qa import NOT_FOUND_ANSWER


def _registry(n: int = 3) -> EvidenceRegistry:
    registry = EvidenceRegistry()
    for i in range(n):
        registry.register(
            Document(
                page_content=f"第{i + 1}段内容",
                metadata={
                    "doc_id": "d",
                    "chunk_index": i,
                    "chunk_id": f"d:{i}",
                    "source": "a.txt",
                    "page": None,
                },
            )
        )
    return registry


@pytest.mark.parametrize(
    "answer,expected",
    [
        # 重编后一律从 [1] 开始，与原始的 E 编号无关
        ("结论 [E1]", "结论 [1]"),
        ("结论 【E2】", "结论 [1]"),
        ("结论 [ E3 ]", "结论 [1]"),
        ("结论 [E1, E2]", "结论 [1][2]"),
        ("结论 [E1、E2]", "结论 [1][2]"),
        ("结论 [E1-E3]", "结论 [1][2][3]"),
        ("结论 [E1 - E2]", "结论 [1][2]"),
    ],
)
def test_various_citation_styles_are_rewritten(answer, expected):
    """模型的各种引用写法都要被识别并重编，不能把原文留在回答里。"""
    clean, sources, grounded = _registry().finalize(answer)

    assert clean == expected
    assert grounded is True
    assert "[E" not in clean and "【" not in clean
    # sources 顺序与编号一致
    assert [s["index"] for s in sources] == sorted({s["index"] for s in sources})


def test_fabricated_ids_removed_but_valid_kept():
    """编造的编号剔除，有效编号保留并重编。"""
    clean, sources, _ = _registry().finalize("甲 [E1]，乙 [E9]，丙 [E2]")

    assert clean == "甲 [1]，乙 ，丙 [2]"
    assert [s["index"] for s in sources] == [1, 2]
    assert sources[0]["snippet"] == "第1段内容"
    assert sources[1]["snippet"] == "第2段内容"


def test_range_with_fabricated_tail():
    """范围里混着不存在的编号时，只保留有效部分。"""
    clean, _, _ = _registry(2).finalize("结论 [E1-E5]")

    assert clean == "结论 [1][2]"


def test_all_fabricated_leaves_no_marker():
    """全是编造编号时整段引用被删除。"""
    clean, sources, grounded = _registry().finalize("结论 [E99]")

    assert clean == "结论"
    assert sources == []
    assert grounded is False


def test_citation_index_order_follows_first_appearance():
    """先出现的编号拿 1。"""
    clean, sources, _ = _registry().finalize("先说 [E3]，再说 [E1]")

    assert clean == "先说 [1]，再说 [2]"
    assert sources[0]["snippet"] == "第3段内容"
    assert sources[1]["snippet"] == "第1段内容"


# ---------- 未找到判定收紧 ----------


def test_exact_not_found_answer_is_grounded():
    clean, sources, grounded = _registry().finalize(NOT_FOUND_ANSWER)

    assert clean == NOT_FOUND_ANSWER
    assert sources == []
    assert grounded is True


def test_not_found_phrase_inside_answer_is_not_grounded():
    """原实现用 `in` 判断，这类回答会被错误放行。"""
    answer = "公司成立于 1998 年。股东结构文档未找到"

    _, _, grounded = _registry().finalize(answer)

    assert grounded is False, "混着无引用结论的回答不应判为有依据"


def test_negated_not_found_is_not_grounded():
    answer = "并非未找到，答案是 42"

    _, _, grounded = _registry().finalize(answer)

    assert grounded is False


def test_not_found_with_extra_sentence_is_not_grounded():
    answer = NOT_FOUND_ANSWER + "建议补充相关资料。"

    _, _, grounded = _registry().finalize(answer)

    assert grounded is False, "话术后面追加内容就不算标准话术了"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("文档中未找到相关信息。", True),
        ("文档中未找到相关信息", True),
        ("  文档中未找到相关信息！ ", True),
        ("文档中未找到相关信息。补充一句", False),
        ("公司成立于1998年。股东结构文档未找到", False),
        ("", False),
    ],
)
def test_is_not_found_boundary(text, expected):
    assert _is_not_found(text) is expected


# ---------- 编号展开 ----------


@pytest.mark.parametrize(
    "group,expected",
    [
        ("E1", [1]),
        ("E1, E3", [1, 3]),
        ("E1、E3", [1, 3]),
        ("E1-E3", [1, 2, 3]),
        ("E3-E1", [1, 2, 3]),
        ("E2 - E4", [2, 3, 4]),
    ],
)
def test_expand_numbers(group, expected):
    assert _expand_numbers(group) == expected


def test_expand_numbers_huge_range_not_exploded():
    """跨度太大时只取两端，避免模型写出 [E1-E9999] 撑爆内存。"""
    numbers = _expand_numbers("E1-E9999")

    assert numbers == [1, 9999]


def test_plain_bracket_numbers_not_treated_as_citation():
    """普通方括号数字（如 [1]、[2024]）不是证据引用，不应被处理。"""
    clean, sources, _ = _registry().finalize("参考价格表 [1] 与年份 [2024]。")

    assert clean == "参考价格表 [1] 与年份 [2024]。"
    assert sources == []
