FROM python:3.11-slim

# Playwright Chromium 浏览器路径（供 appuser 读取）
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 设置工作目录
WORKDIR /app

# 系统依赖：编译器 + Playwright/Chromium 运行时库
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    # Chromium 运行时依赖（Playwright 需要）
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --timeout 300 --retries 5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 安装 Playwright Chromium 浏览器（必须在 USER appuser 之前）
RUN mkdir -p /opt/playwright && \
    playwright install chromium && \
    chown -R appuser:appgroup /opt/playwright

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
