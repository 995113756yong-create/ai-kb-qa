"""AgentStore.create 的并发安全。

原实现的「已存在」检查在锁外、写入在锁内，两个请求同时用同一个 ID
创建时都能通过检查，后写入的会静默覆盖前一个。
"""
from concurrent.futures import ThreadPoolExecutor

from app.agent_store import AgentStore


def _store(tmp_path, embeddings) -> AgentStore:
    return AgentStore(
        str(tmp_path / "agents_store"),
        str(tmp_path / "uploads"),
        str(tmp_path / "faiss_index"),
        str(tmp_path / "logs"),
        embeddings,
    )


def test_concurrent_create_same_id_only_one_wins(tmp_path, embeddings):
    """10 个线程同时用同一个 agent_id 创建，只能有 1 个成功。"""
    store = _store(tmp_path, embeddings)

    def attempt(_i: int) -> bool:
        try:
            store.create(name="并发测试", agent_id="dup")
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(10)))

    assert sum(results) == 1, f"应恰好 1 次成功，实际 {sum(results)} 次"
    assert results.count(False) == 9

    # 落盘的也只有一个
    entries = [a for a in store.list_agents() if a["agent_id"] == "dup"]
    assert len(entries) == 1


def test_create_duplicate_sequential_still_rejected(tmp_path, embeddings):
    """顺序重复创建仍被拒绝（不能因为加了锁内检查就漏掉快速失败）。"""
    store = _store(tmp_path, embeddings)
    store.create(name="第一个", agent_id="seq")

    try:
        store.create(name="第二个", agent_id="seq")
    except ValueError as e:
        assert "已存在" in str(e)
    else:
        raise AssertionError("重复创建应抛 ValueError")
