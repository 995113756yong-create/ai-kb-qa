FROM python:3.12-slim

WORKDIR /app/backend

# 先装依赖，代码改动时能复用缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 工作目录保持 /app/backend，Sealos 上的持久卷路径（uploads / faiss_index）不受影响
COPY app ./app

# 运行期目录，容器里挂卷覆盖
RUN mkdir -p uploads faiss_index logs

# 云平台用 PORT 环境变量指定端口，默认 8000
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
