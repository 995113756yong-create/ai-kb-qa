import subprocess

subprocess.run(["git", "add", "-A"], check=True)
msg = """fix(frontend): 证据编号错位与 chunk 接口契约 (M0)

M0.1 证据编号错位一位
回答里的引用 [n] 从 1 开始, Source.index 也从 1 开始, 但前端把 n 当数组下标用:
- MessageList 原样传给 onJumpToSource(message.id, index)
- EvidencePanel 用 sources[index] 取证据, 点 [1] 拿到第 2 条; 只有一条证据时
  拿到 undefined, 面板显示"点击回答中的引用编号查看证据原文"
- 标题又写 source.index + 1, 编号多加了一次

修法: 全链路统一传引用编号 n (从 1 开始), 新增 sourceByCitation 按 index 查找,
禁止数组下标. citations.ts 的 CITATION_RE 同时接受 [1] 与 [E1] -- 正文最终是 [1],
流式中断时可能残留 [E1].

M0.2 "展开上下文" 前后端接口对不上
- getChunk 传的是 window, 后端读的是 neighbors, 参数被忽略
- ChunkResponse 类型是 { status, chunk_id, text, neighbors:{before,after} },
  后端实际是 { status, chunk: {...} }, 于是 res.text 恒为 undefined

修法: 以<后端为准>改前端. getChunk 参数改为 neighbors; ChunkDetail/ChunkResponse
按后端实际结构重写; EvidencePanel 改读 res.chunk.content.

验收: typecheck 0 error, lint 0 error 0 warning, 67 项测试通过, build 成功.
新增 citations.test.ts (8 项, 覆盖单条证据/非连续编号) 与 api.test.ts 的 getChunk 3 项.
"""
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit", p.returncode)
print(p.stdout[-300:])
print(subprocess.run(["git", "show", "--stat", "--oneline", "HEAD"], capture_output=True, text=True, encoding="utf-8").stdout)
