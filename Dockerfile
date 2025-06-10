# ---- Stage 1: Builder ----
# 使用一个完整的 Python 镜像来构建依赖
FROM python:3.9-slim AS builder

WORKDIR /app

# 安装编译所需的依赖 (以防某些库需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境，隔离依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制需求文件并安装依赖
# 这样可以利用 Docker 的层缓存
COPY requirements.txt .
# 确保 gevent 已安装
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: Final Image ----
# 使用一个非常轻量的基础镜像
FROM python:3.9-slim

# 创建非 root 用户和组
RUN groupadd -r appgroup -g 1001 && \
    useradd -r -u 1001 -g appgroup -m -d /home/appuser -s /bin/bash appuser

# 设置工作目录
WORKDIR /app

# 从 builder 阶段复制已安装的虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY --chown=appuser:appgroup . .

# 创建应用需要的目录并设置权限
RUN mkdir -p /app/knowledge_base /app/logs && \
    chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 1011

# 启动命令
# 使用 gunicorn 配置文件来启动，并通过 wsgi.py 入口
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:application"]