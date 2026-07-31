# ============================================================
# 阶段 1：构建阶段（包含编译器，最终镜像不保留）
# ============================================================
FROM python:3.12-slim AS builder

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 构建依赖：编译器 + 运行时库（Playwright 安装需要运行时库才能下载浏览器）
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    # Playwright Chromium 运行时依赖（也用于 playwright install）
    libnss3 libnspr4 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libcurl4 libxshmfence1 \
    # Playwright Chromium 额外渲染依赖
    libgdk-pixbuf-2.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制应用代码
COPY main.py .
COPY backend/ ./backend/
COPY pyproject.toml uv.lock ./

# 一次性安装依赖 + 项目自身
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable && \
    # 验证关键包已安装（构建时发现缺失立即失败）
    uv run python -c "import pymupdf; print('pymupdf:', pymupdf.__version__)" && \
    uv run python -c "import faiss; print('faiss ok')" && \
    uv run python -c "import sentence_transformers; print('sbert ok')"

# 安装 Playwright Chromium 浏览器
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN mkdir -p /opt/playwright && \
    uv run playwright install chromium

# 清理构建时残留（减小镜像层体积）
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -name "*.pyc" -delete 2>/dev/null || true

# ============================================================
# 阶段 2：运行阶段（仅运行时依赖，无编译器）
# ============================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

WORKDIR /app

# 仅安装运行时库（无 gcc/g++）
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libcurl4 libxshmfence1 \
    libgdk-pixbuf-2.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 先创建用户和目录（避免后续 chown 产生 CoW 拷贝）
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser && \
    mkdir -p /app/data /app/logs /opt/playwright

# 从构建阶段复制产物（--chown 避免事后 chown -R 产生 ~6GB 冗余层）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /opt/playwright /opt/playwright

# 复制应用代码
COPY --chown=appuser:appgroup main.py .
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup pyproject.toml uv.lock ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

CMD ["uv", "run", "python", "-u", "main.py"]
