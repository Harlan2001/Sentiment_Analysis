FROM python:3.11-slim

# 安装 uv（从官方镜像复制二进制文件）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Playwright Chromium 浏览器路径（供 appuser 读取）
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/app/.uv-cache

# 设置工作目录
WORKDIR /app

# 系统依赖：编译器 + Playwright/Chromium 运行时库
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
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
    libcurl4 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# 第一层：仅安装依赖（利用 Docker 层缓存：pyproject.toml / uv.lock 不变则命中缓存）
# uv 自动读取 pyproject.toml 中配置的清华大学 PyPI 镜像源
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# 复制应用代码
COPY main.py .
COPY backend/ ./backend/
COPY pyproject.toml uv.lock ./

# 第二层：安装项目本身
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# 安装 Playwright Chromium 浏览器（必须在 USER appuser 之前）
RUN mkdir -p /opt/playwright && \
    uv run playwright install chromium && \
    chown -R appuser:appgroup /opt/playwright

# 创建数据目录并设置权限
RUN mkdir -p /app/data /app/logs /app/.uv-cache && \
    chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# 启动应用
CMD ["uv", "run", "python", "-u", "main.py"]
