import io

src = '''"""参考模式下「未找到」类句子的引用清理.

没找到的东西不可能有出处: 声明知识库里没有某项信息的句子不应带引用,
否则会被判成 grounded, 与语义矛盾.
"""
from app.agent.evidence import EvidenceRegistry, _drop_citations_on_absence
from app.document import load_and_split


def _registry(tmp_path, embeddings) -> EvidenceRegistry:
    reg = EvidenceRegistry()
    path = tmp_path / "a.txt"
    path.write_text("产品 A 的月费是 99 元。产品 B 的月费是 50 元。", encoding="utf-8")
    chunks = load_and_split(str(path), "d0", "a.txt")
    reg.register_many(chunks)
    return reg


def test_absence_sentence_drops_citations(tmp_path, embeddings):
    """「证据中均未出现」这类句子清掉引用, sources 为空."""
    reg = _registry(tmp_path, embeddings)
    clean, sources, grounded = reg.finalize("现有证据中均未出现配置 9999 [E1][E2]。")

    assert "[" not in clean
    assert sources == []
    assert grounded is True  # 属于「未找到」类回答


def test_real_negation_keeps_citation(tmp_path, embeddings):
    """「产品 A 没有免费试用」是事实陈述, 引用要保留."""
    reg = _registry(tmp_path, embeddings)
    clean, sources, _ = reg.finalize("产品 A 没有免费试用 [E1]。")

    assert "[1]" in clean
    assert len(sources) == 1


def test_mixed_sentences_only_absence_loses_citation(tmp_path, embeddings):
    """只有「知识库中没有年费信息」这句丢引用, 后面的事实句保留."""
    reg = _registry(tmp_path, embeddings)
    clean, sources, _ = reg.finalize("知识库中没有年费信息。产品 A 月费 99 元 [E1]。")

    assert "知识库中没有年费信息。" in clean
    assert "[1]" in clean
    assert len(sources) == 1


def test_absence_regex_covers_reference_mode_wording():
    """prompt 允许的各种「没有」措辞都要覆盖到."""
    for text in [
        "知识库中暂无相关资料。",
        "文档里未找到配置 9999。",
        "证据未覆盖这部分。",
        "资料不包含该字段。",
    ]:
        assert _drop_citations_on_absence(text) == text  # 本来就没引用, 原样返回
        cleaned = _drop_citations_on_absence(text[:-1] + " [E1]。")
        assert "[" not in cleaned, f"未清理: {text}"
'''

io.open("backend/tests/test_absence_citation.py", "w", encoding="utf-8", newline="").write(src)
print("written")

import py_compile
py_compile.compile("backend/tests/test_absence_citation.py", doraise=True)
print("compiles OK")