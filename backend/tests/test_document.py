import numbers

from app.document import KnowledgeBase, load_and_split


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _add(kb, tmp_path, name, text, doc_id):
    chunks = load_and_split(_write(tmp_path, name, text), doc_id, name)
    kb.add_document(doc_id, name, len(text), chunks)
    return chunks


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_split_attaches_metadata(tmp_path):
    path = _write(tmp_path, "a.txt", "第一段内容。" * 300)
    chunks = load_and_split(path, doc_id="d1", source="原始文件名.txt")
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.metadata == {
            "doc_id": "d1",
            "source": "原始文件名.txt",
            "page": None,
            "chunk_index": i,
            "chunk_id": f"d1:{i}",
        }
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


def test_every_chunk_has_chunk_id(tmp_path, embeddings):
    """每个片段都有稳定的 chunk_id，格式为 doc_id:chunk_index。"""
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    chunks = _add(kb, tmp_path, "a.txt", "第一段内容。" * 300, "d1")

    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.metadata["chunk_id"] == f"d1:{i}"
        assert kb.get_chunk(f"d1:{i}").page_content == chunk.page_content

    assert kb.get_chunk("d1:999") is None


def test_get_neighbors_bounds(tmp_path, embeddings):
    """第一个片段没有前一个，最后一个没有后一个，window 越大取到的越多。"""
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    _add(kb, tmp_path, "a.txt", "第一段内容。" * 300, "d1")

    total = len(kb.search("第一段内容", k=100))
    last_index = total - 1

    # 第一个片段只有自己和后一个；最后一个只有自己和前一个
    assert [d.metadata["chunk_index"] for d in kb.get_neighbors("d1:0")] == [0, 1]
    assert [d.metadata["chunk_index"] for d in kb.get_neighbors(f"d1:{last_index}")] == [
        last_index - 1,
        last_index,
    ]
    # window 变大后覆盖范围随之变大，但不会越界
    assert [d.metadata["chunk_index"] for d in kb.get_neighbors("d1:0", window=10)] == list(
        range(total)
    )
    # 不存在的片段返回空
    assert kb.get_neighbors("d1:999") == []


def test_search_with_scores_filters_by_doc(tmp_path, embeddings):
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    _add(kb, tmp_path, "a.txt", "苹果是一种水果", "da")
    _add(kb, tmp_path, "b.txt", "苹果是手机品牌", "db")

    hits = kb.search_with_scores("苹果", k=5, doc_id="db")
    assert hits
    assert all(doc.metadata["doc_id"] == "db" for doc, _ in hits)
    assert all(isinstance(score, numbers.Real) for _, score in hits)


def test_delete_document_removes_chunks_and_survives_reload(tmp_path, embeddings):
    """删除后检索不到被删文档，重启（重新构造 KnowledgeBase）后依然只剩另一份。"""
    index_dir = str(tmp_path / "idx")
    kb = KnowledgeBase(index_dir, embeddings)
    _add(kb, tmp_path, "a.txt", "苹果是一种水果", "da")
    _add(kb, tmp_path, "b.txt", "火星是一颗行星", "db")

    removed = kb.delete_document("da")
    assert removed is not None and removed["doc_id"] == "da"
    assert [d["doc_id"] for d in kb.list_documents()] == ["db"]
    assert all(d.metadata["doc_id"] != "da" for d in kb.search("苹果是一种水果", k=10))

    reloaded = KnowledgeBase(index_dir, embeddings)
    assert [d["doc_id"] for d in reloaded.list_documents()] == ["db"]
    assert all(d.metadata["doc_id"] == "db" for d in reloaded.search("任意问题", k=10))
    assert reloaded.delete_document("da") is None


def test_delete_last_document_resets_kb(tmp_path, embeddings):
    """删掉唯一文档后知识库为空，再上传可以正常重建索引。"""
    index_dir = tmp_path / "idx"
    kb = KnowledgeBase(str(index_dir), embeddings)
    _add(kb, tmp_path, "a.txt", "苹果是一种水果", "da")

    assert kb.delete_document("da") is not None
    assert kb.is_empty
    assert not (index_dir / "index.faiss").exists()
    assert kb.search("苹果", k=3) == []

    _add(kb, tmp_path, "b.txt", "火星是一颗行星", "db")
    assert not kb.is_empty
    assert kb.search("火星是一颗行星", k=1)[0].metadata["doc_id"] == "db"


def test_legacy_index_is_backed_up(tmp_path, embeddings):
    """旧格式索引（无 docs.json 或没有 version 字段）整体改名备份，以空库启动。"""
    index_dir = tmp_path / "idx"
    kb = KnowledgeBase(str(index_dir), embeddings)
    _add(kb, tmp_path, "a.txt", "苹果是一种水果", "da")

    # 造一个 v1 格式的清单
    (index_dir / "docs.json").write_text(
        '[{"doc_id": "da", "filename": "a.txt", "chunks": 1}]', encoding="utf-8"
    )

    reloaded = KnowledgeBase(str(index_dir), embeddings)
    assert reloaded.is_empty
    assert reloaded.list_documents() == []

    backups = [p for p in tmp_path.iterdir() if p.name.startswith("idx.legacy-")]
    assert len(backups) == 1
    assert (backups[0] / "index.faiss").exists()
