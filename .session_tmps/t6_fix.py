import io

p = "backend/app/agent_store.py"
t = io.open(p, encoding="utf-8").read()

old = """        with self._lock:
            self._agents[agent_id] = entry
            self._save()
        return dict(entry)"""

new = """        with self._lock:
            # 锁内再查一次：上面那次检查在锁外，两个请求同时用同一个 ID 创建时
            # 都能通过，后写入的会覆盖前一个。
            if agent_id in self._agents:
                raise ValueError(f"agent_id 已存在：{agent_id}")
            self._agents[agent_id] = entry
            self._save()
        return dict(entry)"""

assert old in t, "create lock block not found"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("agent_store.create fixed")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")