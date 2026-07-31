# ============================================================
# Stage 1: Builder
# ============================================================
FROM python:3.12.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# 安装 uv（使用 pip 替代 ghcr.io 镜像，避免国内 TLS 超时）
RUN pip install uv --no-cache-dir https://mirrors.aliyun.com/pypi/simple

WORKDIR /app


# ------------------------------------------------------------
# 构建依赖
# ------------------------------------------------------------
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*


# ------------------------------------------------------------
# 安装 Python 依赖
# 利用 Docker BuildKit cache
# ------------------------------------------------------------
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project


# ------------------------------------------------------------
# 复制项目
# ------------------------------------------------------------
COPY main.py .
COPY backend/ ./backend/
COPY pyproject.toml uv.lock ./


RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


# ------------------------------------------------------------
# 安装 Playwright Chromium
# ------------------------------------------------------------
RUN mkdir -p /opt/playwright \
    && uv run playwright install chromium


# ------------------------------------------------------------
# 清理
# ------------------------------------------------------------
RUN find /app/.venv \
        -type d \
        \( -name "__pycache__" -o -name "tests" \) \
        -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv \
        -name "*.pyc" \
        -delete



# ============================================================
# Stage 2: Runtime
# ============================================================
FROM python:3.12.11-slim-bookworm AS runtime


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    HOME=/home/appuser \
    PATH="/app/.venv/bin:$PATH"


WORKDIR /app



# ------------------------------------------------------------
# Runtime依赖
# ------------------------------------------------------------
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        tini \
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
        libgdk-pixbuf-2.0-0 \
        libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*



# ------------------------------------------------------------
# 创建运行用户
# ------------------------------------------------------------
RUN groupadd -r appgroup \
    && useradd \
        -r \
        -g appgroup \
        -u 1000 \
        -m \
        -d /home/appuser \
        appuser \
    && mkdir -p \
        /app/data \
        /app/logs \
        /opt/playwright \
        /home/appuser/.cache \
    && chown -R appuser:appgroup \
        /app \
        /opt/playwright \
        /home/appuser



# ------------------------------------------------------------
# 复制构建产物
# ------------------------------------------------------------
COPY --from=builder \
     --chown=appuser:appgroup \
     /app/.venv \
     /app/.venv


COPY --from=builder \
     --chown=appuser:appgroup \
     /opt/playwright \
     /opt/playwright



# ------------------------------------------------------------
# 复制业务代码
# ------------------------------------------------------------
COPY --chown=appuser:appgroup main.py .

COPY --chown=appuser:appgroup backend/ ./backend/

COPY --chown=appuser:appgroup \
     pyproject.toml \
     uv.lock \
     ./



USER appuser



EXPOSE 8000



# ------------------------------------------------------------
# Health Check
# ------------------------------------------------------------
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=40s \
    --retries=3 \
    CMD python -c "\
import urllib.request;\
urllib.request.urlopen(\
'http://localhost:8000/health',\
timeout=5\
)" || exit 1



# ------------------------------------------------------------
# tini:
# 负责 SIGTERM 转发、僵尸进程回收
# ------------------------------------------------------------
ENTRYPOINT ["tini","--"]


CMD ["python","-u","main.py"]