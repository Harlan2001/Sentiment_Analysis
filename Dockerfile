# Python 3.11
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --timeout 300 --retries 5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --no-cache-dir \
    -r requirements.txt

# 复制应用代码
COPY main.py .
COPY backend/ ./backend/

# 创建数据目录并设置权限
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# 启动应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
