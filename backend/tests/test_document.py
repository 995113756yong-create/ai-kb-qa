from app.document import KnowledgeBase, load_and_split


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_split_attaches_metadata(tmp_path):
    path = _write(tmp_path, "a.txt", "第一段内容。" * 300)
    chunks = load_and_split(path, doc_id="d1", source="原始文件名.txt")
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.metadata == {"doc_id": "d1", "source": "原始文件名.txt", "page": None, "chunk_index": i}
        assert len(c.page_content) <= 500


def test_second_upload_does_not_overwrite_first(tmp_path, embeddings):
    """回归测试：原实现每次上传都新建索引，旧文档会被覆盖。"""
    index_dir = str(tmp_path / "idx")
    kb = KnowledgeBase(index_dir, embeddings)

    a = load_and_split(_write(tmp_path, "a.txt", "苹果是一种水果"), "da", "a.txt")
    b = load_and_split(_write(tmp_path, "b.txt", "火星是一颗行星"), "db", "b.txt")
    kb.add_document("da", "a.txt", 10, a)
    kb.add_document("db", "b.txt", 10, b)

    assert kb.search("苹果是一种水果", k=1)[0].metadata["doc_id"] == "da"
    assert kb.search("火星是一颗行星", k=1)[0].metadata["doc_id"] == "db"

    # 重新加载（模拟服务重启），两份文档都还在
    reloaded = KnowledgeBase(index_dir, embeddings)
    assert [d["doc_id"] for d in reloaded.list_documents()] == ["da", "db"]
    ids = {d.metadata["doc_id"] for d in reloaded.search("任意问题", k=10)}
    assert ids == {"da", "db"}


def test_empty_kb(tmp_path, embeddings):
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    assert kb.is_empty
    assert kb.search("x", k=3) == []
    assert kb.list_documents() == []
