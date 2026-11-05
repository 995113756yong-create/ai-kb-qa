import io

p = "README.md"
t = io.open(p, encoding="utf-8").read()

anchor = (
    "- 前端镜像 `ghcr.io/995113756yong-create/ai-kb-qa-web:latest`，"
    "容器端口 3000，开启公网访问，环境变量 `BACKEND_URL=http://ai-kb-qa:8000`"
    "（以 Sealos 控制台显示的内网地址为准）"
)
assert anchor in t, "sealos anchor not found"

addition = anchor + (
    "\n- **后端 Service 不要配置公网 Ingress**：只允许前端在集群内访问。"
    "后端限流依赖 `TRUST_PROXY=true` 取 XFF 判断客户端 IP，"
    "一旦后端可被公网直连，客户端就能自行伪造 X-Forwarded-For 绕过限流。"
    "本地 `docker-compose.prod.yml` 已把后端端口绑到 `127.0.0.1`。"
)
t = t.replace(anchor, addition, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("README sealos section updated")