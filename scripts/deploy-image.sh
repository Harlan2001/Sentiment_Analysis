#!/bin/bash
# =============================================================================
# 完整镜像部署脚本（在构建机上执行）
# 构建前后端镜像 → 导出 → 传输 → 服务器 load 并重启
# 同时传输 docker-compose + 环境变量 + 定时任务脚本
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

BE_TAR="sentiment-backend.tar.gz"
FE_TAR="sentiment-frontend.tar.gz"

# ======================== 部署函数 ========================
deploy_images_to() {
    local TARGET="$1"
    local SERVER_HOST="${HOST[$TARGET]}"
    local SERVER_USER="${USER[$TARGET]}"
    local SERVER_PATH="${SERVER_PATH[$TARGET]}"
    local SSH_CMD
    local SCP_CMD

    if [ "${IS_SAAS[$TARGET]}" = "true" ]; then
        SSH_CMD=(ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p")
        SCP_CMD=(scp -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p")
    else
        SSH_CMD=(ssh)
        SCP_CMD=(scp)
    fi

    echo ""
    echo "──────────────────────────────────────"
    echo "  目标: $TARGET → $SERVER_USER@$SERVER_HOST"
    echo "──────────────────────────────────────"

    # --- 构建配置文件包 ---
    echo ""
    echo "  [1/5] 构建配置文件包..."

    local TMPDIR
    TMPDIR="$(mktemp -d)"

    # 环境变量文件（release/{target}.env → .env）
    cp "release/${TARGET}.env" "$TMPDIR/.env"

    # docker-compose
    cp docker-compose.yml "$TMPDIR/"

    # 定时任务脚本（去掉环境后缀）
    mkdir -p "$TMPDIR/scripts"
    for f in scripts/deploy/*_${TARGET}.sh; do
        local basename="${f##*/}"
        local newname="${basename%_${TARGET}.sh}.sh"
        cp "$f" "$TMPDIR/scripts/$newname"
    done

    local CONFIG_TAR="/tmp/sentiment-config-${TARGET}.tar.gz"
    tar -czf "$CONFIG_TAR" -C "$TMPDIR" .
    rm -rf "$TMPDIR"

    echo "  ✓ 配置文件包构建完成"

    # --- 传输镜像 + 配置文件 ---
    echo ""
    echo "  [2/5] 传输镜像和配置文件..."

    "${SCP_CMD[@]}" "$BE_TAR" "$FE_TAR" "$CONFIG_TAR" \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"

    rm -f "$CONFIG_TAR"

    echo "  ✓ 传输完成 (后端: $(du -h $BE_TAR | cut -f1), 前端: $(du -h $FE_TAR | cut -f1))"

    # --- 加载镜像 + 解包配置 ---
    echo ""
    echo "  [3/5] 加载镜像..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
echo "  加载后端镜像..."
gunzip -c ${BE_TAR} | docker load
echo "  加载前端镜像..."
gunzip -c ${FE_TAR} | docker load
rm -f ${BE_TAR} ${FE_TAR}
REMOTE_EOF

    echo "  ✓ 镜像加载完成"

    # --- 解包配置文件 ---
    echo ""
    echo "  [4/5] 解包配置文件..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
# 先删旧配置/脚本再解压 —— 被删除的配置/脚本才会同步移除
# data/ logs/ models/（挂载卷）不在此包内，保留不动
rm -rf docker-compose.yml .env scripts
tar -xzf sentiment-config-${TARGET}.tar.gz
rm sentiment-config-${TARGET}.tar.gz
REMOTE_EOF

    echo "  ✓ 配置文件解包完成"

    # --- 重启服务 ---
    echo ""
    echo "  [5/5] 重启服务..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
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
echo "  完整镜像部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 1. 构建镜像（用 --build-arg 破坏源码层缓存，保留 npm ci 层缓存）
echo ""
echo "=== [构建] 构建镜像 ==="
docker compose build --build-arg CACHEBUST="$(date +%s)" --progress=plain

# 2. 导出镜像
echo ""
echo "=== [导出] 导出镜像 ==="
docker save sentiment-backend:latest | gzip > "$BE_TAR"
docker save sentiment-frontend:latest | gzip > "$FE_TAR"

echo "  后端镜像: $(du -h $BE_TAR | cut -f1)"
echo "  前端镜像: $(du -h $FE_TAR | cut -f1)"

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
rm -f "$BE_TAR" "$FE_TAR"

echo ""
echo "========================================"
echo "  镜像部署完成"
echo "========================================"
