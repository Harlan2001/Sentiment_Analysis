#!/bin/bash
# =============================================================================
# 快速部署脚本（在构建机上执行）
# 只传后端代码 + 重启容器，不传完整镜像
#
# 用法：
#   ./scripts/deploy.sh               # 部署到大前台
#   ./scripts/deploy.sh saas          # 部署到 Saas（京东云，需跳板机）
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
    SSH_CMD_PREFIX="ssh -o ProxyCommand='ssh -p 2222 root@114.67.114.200 -W %h:%p'"
else
    SERVER_HOST="10.253.50.112"
    SERVER_USER="admin"
    SERVER_PATH="/opt/sentiment/deploy"
    SSH_CMD_PREFIX="ssh"
fi

echo "========================================"
echo "  Sentiment 快速部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  目标: $TARGET → $SERVER_USER@$SERVER_HOST"
echo "========================================"

# ========================
# 第一步：传输后端代码
# ========================
echo ""
echo "=== [1/2] 传输后端代码 ==="

RSYNC_OPTS="-avz --delete --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store'"

if [ "$TARGET" = "saas" ]; then
    # Saas 需要跳板机，改用 scp（rsync over ssh 在跳板机场景复杂）
    tar -czf /tmp/sentiment-code.tar.gz main.py backend/
    scp -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" \
        /tmp/sentiment-code.tar.gz \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" \
        "${SERVER_USER}@${SERVER_HOST}" \
        "cd ${SERVER_PATH} && tar -xzf sentiment-code.tar.gz && rm sentiment-code.tar.gz"
    rm -f /tmp/sentiment-code.tar.gz
else
    rsync $RSYNC_OPTS main.py backend/ "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
fi

echo "  传输完成"

# ========================
# 第二步：重启服务
# ========================
echo ""
echo "=== [2/2] 重启后端 ==="

if [ "$TARGET" = "saas" ]; then
    ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" \
        "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /data/sentiment_deploy
echo "  重启容器..."
docker compose restart backend
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF
else
    ssh "${SERVER_USER}@${SERVER_HOST}" << 'REMOTE_EOF'
cd /opt/sentiment/deploy
echo "  重启容器..."
docker compose restart backend
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF
fi

echo ""
echo "========================================"
echo "  部署完成"
echo "  目标: $TARGET"
echo "========================================"
