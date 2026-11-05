import io

p = "README.md"
t = io.open(p, encoding="utf-8").read()

old = "每个请求结束（成功或失败）都向 `AGENT_LOG_DIR/agent_runs.jsonl` 追加一行："
new = (
    "每个请求结束都向 `AGENT_LOG_DIR/agent_runs.jsonl` 追加一行，包括成功、失败，"
    "以及用户点「停止」或浏览器断连的请求。停止的记录多一个 `\"stopped\": true` 字段，"
    "`answer` 是已经生成的部分回答，`evidence_count` 为 null（中途关闭时还没扫完证据）："
)
assert old in t, "README log section not found"
t = t.replace(old, new, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("README log section updated")