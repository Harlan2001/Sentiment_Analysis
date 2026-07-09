#!/bin/bash
# =============================================================================
# 快速部署脚本（在构建机上执行）
# 只传后端代码 + 重启容器，不传完整镜像
#
# 用法：
#   ./scripts/deploy.sh bigfrontend   # 部署到大前台
#   ./scripts/deploy.sh saas          # 部署到 Saas（京东云，需跳板机）
#   ./scripts/deploy.sh both          # 同时部署两个服务器
# =============================================================================
set -e

# 确保非交互式脚本也能找到系统命令（WSL 兼容）
export PATH="/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ======================== 服务器配置 ========================
declare -A HOST USER SERVER_PATH IS_SAAS

HOST[bigfrontend]="10.253.50.112"
USER[bigfrontend]="admin"
SERVER_PATH[bigfrontend]="/opt/sentiment"
IS_SAAS[bigfrontend]="false"

HOST[saas]="172.18.0.23"
USER[saas]="root"
SERVER_PATH[saas]="/data/sentiment"
IS_SAAS[saas]="true"

# ======================== 部署函数 ========================
deploy_to() {
    local TARGET="$1"
    local SERVER_HOST="${HOST[$TARGET]}"
    local SERVER_USER="${USER[$TARGET]}"
    local SERVER_PATH="${SERVER_PATH[$TARGET]}"
    local SSH_CMD
    local SCP_CMD

    if [ "${IS_SAAS[$TARGET]}" = "true" ]; then
        SSH_CMD="ssh -o ProxyCommand='ssh -p 2222 root@114.67.114.200 -W %h:%p'"
        SCP_CMD="scp -o ProxyCommand='ssh -p 2222 root@114.67.114.200 -W %h:%p'"
    else
        SSH_CMD="ssh"
        SCP_CMD="scp"
    fi

    echo ""
    echo "──────────────────────────────────────"
    echo "  目标: $TARGET → $SERVER_USER@$SERVER_HOST"
    echo "──────────────────────────────────────"

    # --- 传输后端代码 ---
    echo ""
    echo "  [1/3] 传输后端代码..."

    RSYNC_OPTS="-avz --delete --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store'"

    if [ "${IS_SAAS[$TARGET]}" = "true" ]; then
        tar -czf /tmp/sentiment-code.tar.gz main.py backend/
        $SCP_CMD /tmp/sentiment-code.tar.gz "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
        $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" \
            "cd ${SERVER_PATH} && tar -xzf sentiment-code.tar.gz && rm sentiment-code.tar.gz"
        rm -f /tmp/sentiment-code.tar.gz
    else
        rsync $RSYNC_OPTS main.py backend/ "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    fi
    echo "  ✓ 代码传输完成"

    # --- 传输定时任务脚本 ---
    echo ""
    echo "  [2/3] 传输定时任务脚本..."

    if [ "${IS_SAAS[$TARGET]}" = "true" ]; then
        tar -czf /tmp/sentiment-cron.tar.gz -C deploy/ .
        $SCP_CMD /tmp/sentiment-cron.tar.gz "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
        $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" \
            "cd ${SERVER_PATH} && tar -xzf sentiment-cron.tar.gz && rm sentiment-cron.tar.gz"
        rm -f /tmp/sentiment-cron.tar.gz
    else
        rsync -avz deploy/ "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    fi
    echo "  ✓ 定时任务脚本传输完成"

    # --- 重启后端 ---
    echo ""
    echo "  [3/3] 重启后端..."

    $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
echo "  重启容器..."
docker compose restart backend
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF

    echo "  ✓ $TARGET 部署完成"
}

# ======================== 主流程 ========================
TARGET="${1:-bigfrontend}"

echo "========================================"
echo "  Sentiment 快速部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

case "$TARGET" in
    both)
        deploy_to "bigfrontend"
        deploy_to "saas"
        ;;
    saas)
        deploy_to "saas"
        ;;
    bigfrontend)
        deploy_to "bigfrontend"
        ;;
    *)
        echo "错误: 未知目标 '$TARGET'，可选: bigfrontend | saas | both"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "  全部部署完成"
echo "========================================"
