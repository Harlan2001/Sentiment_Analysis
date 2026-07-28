#!/bin/bash
# =============================================================================
# 前端镜像部署脚本（在构建机上执行）
# 构建前端镜像 → 导出 → 传输 → 服务器 load 并重启
#
# 用法：
#   ./scripts/deploy_frontend.sh bigfrontend   # 部署到大前台
#   ./scripts/deploy_frontend.sh saas          # 部署到 Saas（京东云，需跳板机）
#   ./scripts/deploy_frontend.sh both          # 同时部署两个服务器
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

IMAGE_NAME="sentiment-frontend"
IMAGE_TAR="${IMAGE_NAME}.tar.gz"

# ======================== 构建前端镜像 ========================
echo "========================================"
echo "  Sentiment 前端镜像部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""
echo "  [构建] 编译前端镜像（--no-cache）..."
docker compose build --no-cache frontend
echo "  ✓ 镜像构建完成"

# ======================== 导出镜像 ========================
echo ""
echo "  [导出] 导出镜像..."
docker save "${IMAGE_NAME}:latest" | gzip > "$IMAGE_TAR"
echo "  ✓ 镜像导出完成: $IMAGE_TAR ($(du -h $IMAGE_TAR | cut -f1))"

# ======================== 部署函数 ========================
deploy_to() {
    local TARGET="$1"
    local SERVER_HOST="${HOST[$TARGET]}"
    local SERVER_USER="${USER[$TARGET]}"
    local SERVER_PATH="${SERVER_PATH[$TARGET]}"
    local SCP_CMD
    local SSH_CMD

    if [ "${IS_SAAS[$TARGET]}" = "true" ]; then
        SCP_CMD=(scp -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p")
        SSH_CMD=(ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p")
    else
        SCP_CMD=(scp)
        SSH_CMD=(ssh)
    fi

    echo ""
    echo "──────────────────────────────────────"
    echo "  目标: $TARGET → $SERVER_USER@$SERVER_HOST"
    echo "──────────────────────────────────────"

    # --- 传输镜像 ---
    echo ""
    echo "  [1/2] 传输镜像..."

    "${SCP_CMD[@]}" "$IMAGE_TAR" "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    echo "  ✓ 传输完成"

    # --- 加载镜像并重启 ---
    echo ""
    echo "  [2/2] 加载镜像并重启前端..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
echo "  加载镜像..."
gunzip -c ${IMAGE_TAR} | docker load
rm -f ${IMAGE_TAR}
echo ""
echo "  重启前端容器..."
docker compose up -d frontend
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF

    echo "  ✓ $TARGET 前端部署完成"
}

# ======================== 主流程 ========================
TARGET="${1:-bigfrontend}"

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

# 清理本地镜像文件
rm -f "$IMAGE_TAR"

echo ""
echo "========================================"
echo "  全部部署完成"
echo "========================================"
