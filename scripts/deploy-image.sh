#!/bin/bash
# =============================================================================
# 完整镜像重建脚本（在构建机上执行）
# 仅在 pyproject.toml / uv.lock 或前端依赖变更时使用
#
# 用法：
#   ./scripts/deploy-image.sh bigfrontend  # 部署到大前台
#   ./scripts/deploy-image.sh saas         # 部署到 Saas（京东云，需跳板机）
#   ./scripts/deploy-image.sh both         # 同时部署两个服务器
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
deploy_images_to() {
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

    # --- 传输镜像 ---
    echo ""
    echo "  传输镜像..."

    $SCP_CMD sentiment-backend.tar.gz sentiment-frontend.tar.gz \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"

    echo "  ✓ 镜像传输完成 (后端: $(du -h sentiment-backend.tar.gz | cut -f1), 前端: $(du -h sentiment-frontend.tar.gz | cut -f1))"

    # --- 传输定时任务脚本 ---
    echo ""
    echo "  传输定时任务脚本..."

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

    # --- 加载镜像 ---
    echo ""
    echo "  加载镜像..."

    $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
echo "  加载后端镜像..."
gunzip -c sentiment-backend.tar.gz | docker load
echo "  加载前端镜像..."
gunzip -c sentiment-frontend.tar.gz | docker load
rm -f sentiment-backend.tar.gz sentiment-frontend.tar.gz
REMOTE_EOF

    echo "  ✓ 镜像加载完成"

    # --- 重启服务 ---
    echo ""
    echo "  重启服务..."

    $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
docker compose up -d --force-recreate
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF

    echo "  ✓ $TARGET 部署完成"
}

# ======================== 主流程 ========================
TARGET="${1:-bigfrontend}"

echo "========================================"
echo "  完整镜像重建 & 传输"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 1. 构建镜像（用 --build-arg 破坏源码层缓存，保留 npm ci 层缓存）
echo ""
echo "=== [构建] 构建镜像 ==="
docker compose build --build-arg CACHEBUST="$(date +%s)" --progress=plain

# 2. 导出镜像
echo ""
echo "=== [导出] 导出镜像 ==="
docker save sentiment-backend:latest | gzip > sentiment-backend.tar.gz
docker save sentiment-frontend:latest | gzip > sentiment-frontend.tar.gz

echo "  后端镜像: $(du -h sentiment-backend.tar.gz | cut -f1)"
echo "  前端镜像: $(du -h sentiment-frontend.tar.gz | cut -f1)"

# 3. 部署到目标服务器
echo ""
echo "=== [部署] 传输并部署 ==="

case "$TARGET" in
    both)
        deploy_images_to "bigfrontend"
        deploy_images_to "saas"
        ;;
    saas)
        deploy_images_to "saas"
        ;;
    bigfrontend)
        deploy_images_to "bigfrontend"
        ;;
    *)
        echo "错误: 未知目标 '$TARGET'，可选: bigfrontend | saas | both"
        exit 1
        ;;
esac

# 清理本地镜像文件
rm -f sentiment-backend.tar.gz sentiment-frontend.tar.gz

echo ""
echo "========================================"
echo "  镜像重建 & 部署完成"
echo "========================================"
