#!/bin/bash
# =============================================================================
# 完整镜像重建脚本（在构建机上执行）
# 仅在 requirements.txt 或前端依赖变更时使用
#
# 用法：
#   ./scripts/deploy-image.sh                   # 默认部署到大前台
#   ./scripts/deploy-image.sh saas              # 部署到 Saas（京东云，需跳板机）
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ======================== 部署目标 ========================
TARGET="${1:-default}"

if [ "$TARGET" = "saas" ]; then
    SERVER_HOST="172.18.0.23"
    SERVER_USER="root"
    SERVER_PATH="/data/sentiment_deploy"
    SSH_PORT="22"
    JUMP_HOST="114.67.114.200"
    JUMP_PORT="2222"
    JUMP_USER="root"
    SSH_CMD="ssh -o ProxyCommand='ssh -p $JUMP_PORT $JUMP_USER@$JUMP_HOST -W %h:%p'"
else
    SERVER_HOST="10.253.50.112"
    SERVER_USER="admin"
    SERVER_PATH="/opt/sentiment/deploy"
    SSH_CMD="ssh"
fi

echo "========================================"
echo "  完整镜像重建 & 传输"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  目标: $TARGET → $SERVER_USER@$SERVER_HOST"
echo "========================================"

# 1. 构建镜像（不带 --no-cache，利用 Docker 层缓存）
echo ""
echo "=== [1/5] 构建镜像 ==="
docker compose build --progress=plain

# 2. 导出镜像
echo ""
echo "=== [2/5] 导出镜像 ==="
docker save sentiment-backend:latest | gzip > sentiment-backend.tar.gz
docker save sentiment-frontend:latest | gzip > sentiment-frontend.tar.gz

echo "  后端镜像: $(du -h sentiment-backend.tar.gz | cut -f1)"
echo "  前端镜像: $(du -h sentiment-frontend.tar.gz | cut -f1)"

# 3. 传输镜像
echo ""
echo "=== [3/5] 传输镜像到服务器 ==="
if [ "$TARGET" = "saas" ]; then
    scp -o "ProxyCommand=ssh -p $JUMP_PORT $JUMP_USER@$JUMP_HOST -W %h:%p" \
        sentiment-backend.tar.gz sentiment-frontend.tar.gz \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
else
    scp sentiment-backend.tar.gz sentiment-frontend.tar.gz \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
fi
rm -f sentiment-backend.tar.gz sentiment-frontend.tar.gz

# 4. 服务器加载 + 重启
echo ""
echo "=== [4/5] 服务器加载镜像 ==="
if [ "$TARGET" = "saas" ]; then
    ssh -o "ProxyCommand=ssh -p $JUMP_PORT $JUMP_USER@$JUMP_HOST -W %h:%p" \
        "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /data/sentiment_deploy
echo "  加载后端镜像..."
gunzip -c sentiment-backend.tar.gz | docker load
echo "  加载前端镜像..."
gunzip -c sentiment-frontend.tar.gz | docker load
rm -f sentiment-backend.tar.gz sentiment-frontend.tar.gz
REMOTE_EOF
else
    ssh "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /opt/sentiment/deploy
echo "  加载后端镜像..."
gunzip -c sentiment-backend.tar.gz | docker load
echo "  加载前端镜像..."
gunzip -c sentiment-frontend.tar.gz | docker load
rm -f sentiment-backend.tar.gz sentiment-frontend.tar.gz
REMOTE_EOF
fi

# 5. 重启服务
echo ""
echo "=== [5/5] 重启服务 ==="
if [ "$TARGET" = "saas" ]; then
    ssh -o "ProxyCommand=ssh -p $JUMP_PORT $JUMP_USER@$JUMP_HOST -W %h:%p" \
        "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /data/sentiment_deploy
docker compose up -d --force-recreate
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF
else
    ssh "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /opt/sentiment/deploy
docker compose up -d --force-recreate
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF
fi

echo ""
echo "========================================"
echo "  镜像重建完成"
echo "  目标: $TARGET"
echo "========================================"
