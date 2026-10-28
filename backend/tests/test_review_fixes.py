import numbers

import pytest

from app.document import KnowledgeBase, load_and_split


def _add(kb, tmp_path, name, text, doc_id):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    chunks = load_and_split(str(path), doc_id, name)
    kb.add_document(doc_id, name, len(text), chunks)
    return chunks


def test_filtered_search_survives_large_sibling(tmp_path, embeddings):
    """P0-1 回归：另一份文档很大时，限定小文档检索不能返回空。

    必须构造「目标文档片段完全不进候选池」的场景才能复现：
    用 DeterministicFakeEmbedding 时，与查询文本完全相同的大文档片段
    会稳稳占满前 fetch_k 名，目标文档就被彻底挤掉了。
    实测 300 片段的大文档 + 2 片段的小文档，修复前返回 0 条。
    """
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document

    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)

    big_docs = [
        Document(
            page_content="报告" * 100,
            metadata={
                "doc_id": "big",
                "chunk_index": i,
                "chunk_id": f"big:{i}",
                "source": "big.txt",
                "page": None,
            },
        )
        for i in range(300)
    ]
    small_docs = [
        Document(
            page_content=f"关于苹果和香蕉的水果说明第{i}段",
            metadata={
                "doc_id": "small",
                "chunk_index": i,
                "chunk_id": f"small:{i}",
                "source": "small.txt",
                "page": None,
            },
        )
        for i in range(2)
    ]

    all_docs = big_docs + small_docs
    kb._store = FAISS.from_documents(
        all_docs, embeddings, ids=[d.metadata["chunk_id"] for d in all_docs]
    )
    kb._docs = [
        {"doc_id": "big", "filename": "big.txt", "chunks": 300},
        {"doc_id": "small", "filename": "small.txt", "chunks": 2},
    ]

    query = "报告" * 100

    # 先确认旧写法确实失效，否则这个测试就失去意义
    broken = kb._store.similarity_search_with_score(
        query, k=3, filter={"doc_id": "small"}, fetch_k=3 * 4
    )
    assert broken == [], "构造的场景没有复现问题，fetch_k 仍然够用"

    hits = kb.search_with_scores(query, k=3, doc_id="small")

    assert len(hits) == 2, f"修复后应能取到小文档的 2 个片段，实际 {len(hits)}"
    assert all(doc.metadata["doc_id"] == "small" for doc, _ in hits)


def test_filtered_search_respects_k(tmp_path, embeddings):
    """限定文档检索也要遵守 k 上限。"""
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    _add(kb, tmp_path, "a.txt", "报告内容。" * 5000, "a")

    hits = kb.search_with_scores("报告", k=2, doc_id="a")
    assert len(hits) <= 2


def test_add_document_does_not_hold_lock_during_embedding(tmp_path):
    """P0-3 回归：算向量时不能持有全局锁，否则上传期间所有检索都被阻塞。"""
    import threading
    import time

    from langchain_core.embeddings import DeterministicFakeEmbedding

    class SlowEmbedding(DeterministicFakeEmbedding):
        """每次 embed 都故意慢 0.4 秒，模拟真实网络调用。"""

        def embed_documents(self, texts):
            time.sleep(0.4)
            return super().embed_documents(texts)

    embeddings = SlowEmbedding(size=32)
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)

    # 先放一份文档进去，让后续检索有东西可查
    path = tmp_path / "seed.txt"
    path.write_text("种子内容", encoding="utf-8")
    kb.add_document("seed", "seed.txt", 4, load_and_split(str(path), "seed", "seed.txt"))

    upload_path = tmp_path / "new.txt"
    upload_path.write_text("新增内容。" * 50, encoding="utf-8")
    chunks = load_and_split(str(upload_path), "new", "new.txt")

    durations = []

    def do_search():
        time.sleep(0.05)  # 确保上传已经进入 embed 阶段
        t0 = time.time()
        kb.search("种子内容", k=1)
        durations.append(time.time() - t0)

    searcher = threading.Thread(target=do_search)
    searcher.start()
    kb.add_document("new", "new.txt", 50, chunks)
    searcher.join()

    assert durations, "检索线程没有跑起来"
    # 上传整体约 0.4 秒；如果锁把检索挡住，耗时也会接近 0.4 秒
    assert durations[0] < 0.2, f"检索被上传阻塞了 {durations[0]:.2f}s，锁范围仍然过大"


def test_add_document_rolls_back_when_save_fails(tmp_path, embeddings, monkeypatch):
    """P1-1 回归：落盘失败时内存状态要回滚，不能出现"内存有、磁盘没有"。"""
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    _add(kb, tmp_path, "a.txt", "第一份文档内容", "d1")

    before_docs = [d["doc_id"] for d in kb.list_documents()]
    before_ntotal = kb._store.index.ntotal

    def boom():
        raise OSError("磁盘写满")

    monkeypatch.setattr(kb, "_save", boom)

    path = tmp_path / "b.txt"
    path.write_text("第二份文档内容", encoding="utf-8")
    chunks = load_and_split(str(path), "d2", "b.txt")

    with pytest.raises(OSError):
        kb.add_document("d2", "b.txt", 10, chunks)

    # 清单和索引都应回到写入前的状态
    assert [d["doc_id"] for d in kb.list_documents()] == before_docs
    assert kb._store.index.ntotal == before_ntotal
    assert kb.get_chunk("d2:0") is None


def test_delete_tolerates_manifest_mismatch(tmp_path, embeddings):
    """P1-2 回归：清单片段数大于索引实际片段数时，删除不能报 500。"""
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    _add(kb, tmp_path, "a.txt", "会被删掉的文档", "gone")
    _add(kb, tmp_path, "b.txt", "要保留的文档", "keep")

    # 人为把清单里的片段数改大，模拟历史脏数据
    for d in kb._docs:
        if d["doc_id"] == "gone":
            d["chunks"] = 5

    removed = kb.delete_document("gone")

    assert removed is not None
    assert [d["doc_id"] for d in kb.list_documents()] == ["keep"]
    assert kb.get_chunk("gone:0") is None


def test_delete_document_api_handles_mismatch(client, dirs):
    """通过接口删除时同样不能 500。"""
    upload_dir, _ = dirs
    r = client.post(
        "/api/upload",
        files={"file": ("a.txt", "内容".encode("utf-8"), "text/plain")},
    )
    doc_id = r.json()["doc_id"]

    kb = client.app.state.kb
    for d in kb._docs:
        if d["doc_id"] == doc_id:
            d["chunks"] = 99

    resp = client.delete(f"/api/docs/{doc_id}")
    assert resp.status_code == 200, resp.text
