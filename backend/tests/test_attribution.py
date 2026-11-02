"""句子级溯源测试：无损切句 / 分类 / 数字一致性 / 比例."""
import pytest

from app.agent.attribution import Attribution, attribute, classify_span, split_spans


SRC_1 = {
    "index": 1,
    "doc_id": "d1",
    "source": "饮食营养基础.txt",
    "page": None,
    "snippet": "力量训练人群每天每公斤体重 1.6-2.2 克蛋白质 [E1]",
    "content": "力量训练人群：每天每公斤体重 1.6-2.2 克蛋白质。优质来源：鸡胸肉、鱼虾、鸡蛋。",
}


# ---------- 无损切句 ----------


def test_split_lossless_various_formats():
    """10 种格式的回答，切句后拼接必须严格等于原文。"""
    samples = [
        "简单一句。",
        "每周训练 3 次。[1]下一句没有标点",
        "第一点；第二点；第三点",
        "带英文句点的数字 2.5 不会被切开。后半句。",
        "- 列表项一 [1]\n- 列表项二 [2]\n- 无引用项",
        "1. 有序列表 [1]\n2. 另一项",
        "## 小标题\n正文内容 [1]。",
        "结尾没有终止符",
        "多行\n\n空行保留\n\n尾行",
        "混合！感叹？问号[1]分号；结尾",
    ]
    for text in samples:
        spans = split_spans(text)
        assert "".join(spans) == text, f"切句有损: {text!r}"


def test_split_empty():
    assert split_spans("") == []


def test_citation_goes_with_previous_sentence():
    spans = split_spans("每周训练 3 次。[1]下一句")
    assert spans[0] == "每周训练 3 次。[1]"
    assert spans[1] == "下一句"


# ---------- 分类 ----------


def test_classify_kb():
    kind, cits, body = classify_span("每周训练 3 次。[1]", {1})
    assert kind == "kb" and cits == [1]


def test_classify_general():
    kind, cits, body = classify_span("蛋白质是三大营养素之一。", set())
    assert kind == "general" and cits == []


def test_classify_neutral_disclaimer():
    kind, _, _ = classify_span("以下为一般知识，非知识库内容。", set())
    assert kind == "neutral"


def test_classify_neutral_heading():
    kind, _, _ = classify_span("一、训练安排：", set())
    assert kind == "neutral"


def test_classify_neutral_short():
    kind, _, _ = classify_span("好的。", set())
    assert kind == "neutral"


def test_classify_invalid_citation_not_kb():
    """引用编号不存在于 sources 时不算 kb 句。"""
    kind, cits, _ = classify_span("每周训练 3 次。[9]", {1})
    assert kind == "general" and cits == []


def test_short_sentence_with_valid_citation_is_kb():
    """很短但带合法引用的句子仍是 kb 句（顺序修复的回归测试）。"""
    kind, cits, _ = classify_span("是 3 次[1]", {1})
    assert kind == "kb"


# ---------- 数字一致性 ----------


def test_number_present_in_evidence_no_warning():
    att = attribute("每天每公斤 1.6-2.2 克蛋白质 [1]。", [SRC_1], "")
    assert att.numeric_warnings == 0


def test_number_fabricated_warns():
    att = attribute("每天每公斤 2.5 克蛋白质 [1]。", [SRC_1], "")
    assert att.numeric_warnings == 1
    assert "2.5" in att.segments[0].warnings[0]


def test_number_from_question_no_warning():
    att = attribute("我 70 公斤的话需要不少 [1]。", [SRC_1], "我 70 公斤应该吃多少蛋白质")
    # 70 来自问题本身，不算编造
    assert all("70" not in w for w in att.segments[0].warnings)


def test_decimal_not_split():
    att = attribute("增长 2.5% [1]。", [SRC_1], "")
    # 2.5 不在证据里 → 应该整条警告而不是拆成 2 和 5
    warnings_text = " ".join(att.segments[0].warnings)
    assert "2.5" in warnings_text


# ---------- 比例与 grounded ----------


def test_ratio_two_kb_one_general():
    # 第三句故意不含"一般知识/参考"等声明词（那会判成 neutral），
    # 用普通内容句验证 general 分类。
    answer = "第一句来自知识库 [1]。第二句也来自知识库 [1]。香蕉富含钾元素有助于代谢。"
    att = attribute(answer, [SRC_1], "")
    assert att.kb_count == 2
    assert att.general_count == 1
    assert att.grounded_ratio == pytest.approx(0.67, abs=0.01)
    assert not att.grounded


def test_all_neutral_ratio_none():
    att = attribute("好的。", [], "")
    assert att.grounded_ratio is None
    assert att.kb_count == 0 and att.general_count == 0


def test_grounding_requires_no_warnings():
    att = attribute("每天每公斤 2.5 克 [1]。", [SRC_1], "")
    assert att.kb_count == 1 and att.general_count == 0
    assert att.numeric_warnings == 1
    assert not att.grounded  # 有数字警告不算完全可信


def test_full_kb_answer_grounded():
    att = attribute("每天每公斤 1.6-2.2 克 [1]。", [SRC_1], "")
    assert att.kb_count == 1 and att.general_count == 0
    assert att.numeric_warnings == 0
    assert att.grounded
