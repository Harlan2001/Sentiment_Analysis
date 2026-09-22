#!/bin/bash
# =============================================================================
# 后端代码快速部署脚本（在构建机上执行）
# 传输后端代码 + docker-compose + 环境变量 + 定时任务脚本，然后重启容器
#
# 用法：
#   ./scripts/deploy_backend_code.sh bigfrontend   # 部署到大前台
#   ./scripts/deploy_backend_code.sh saas          # 部署到 Saas（京东云，需跳板机）
#   ./scripts/deploy_backend_code.sh both          # 同时部署两个服务器
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

    # --- 构建部署包 ---
    echo ""
    echo "  [1/4] 构建部署包..."

    local TMPDIR
    TMPDIR="$(mktemp -d)"

    # 后端代码 + docker-compose
    cp -r main.py backend/ docker-compose.yml "$TMPDIR/"

    # 环境变量文件（release/{target}.env → .env）
    cp "release/${TARGET}.env" "$TMPDIR/.env"

    # 定时任务脚本（去掉环境后缀，如 analysis_fallback_bigfrontend.sh → analysis_fallback.sh）
    mkdir -p "$TMPDIR/scripts"
    for f in scripts/deploy/*_${TARGET}.sh; do
        local basename="${f##*/}"
        local newname="${basename%_${TARGET}.sh}.sh"
        cp "$f" "$TMPDIR/scripts/$newname"
    done

    # 清理编译缓存
    find "$TMPDIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find "$TMPDIR" -type f -name '*.pyc' -delete 2>/dev/null || true

    echo "  ✓ 部署包构建完成"

    # --- 传输 ---
    echo ""
    echo "  [2/4] 传输部署包..."

    local TARBALL="/tmp/sentiment-deploy-${TARGET}.tar.gz"
    tar -czf "$TARBALL" -C "$TMPDIR" .
    "${SCP_CMD[@]}" "$TARBALL" "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    rm -f "$TARBALL"
    rm -rf "$TMPDIR"

    echo "  ✓ 传输完成"

    # --- 解包 ---
    echo ""
    echo "  [3/4] 解包部署文件..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
# 先删旧代码/配置文件再解压 —— 被删除的源文件才会同步移除
# 刻意保留 data/ logs/ models/（挂载卷，不在此包内）
rm -rf main.py backend docker-compose.yml .env scripts
tar -xzf sentiment-deploy-${TARGET}.tar.gz
rm sentiment-deploy-${TARGET}.tar.gz
REMOTE_EOF

    echo "  ✓ 解包完成"

    # --- 重启后端 ---
    echo ""
    echo "  [4/4] 重启后端..."

    "${SSH_CMD[@]}" "${SERVER_USER}@${SERVER_HOST}" << REMOTE_EOF
cd ${SERVER_PATH}
echo "  重启容器..."
docker compose up -d backend mcp
echo ""
echo "  容器状态:"
docker compose ps
REMOTE_EOF

    echo "  ✓ $TARGET 部署完成"
}

# ======================== 主流程 ========================
TARGET="${1:-bigfrontend}"

echo "========================================"
echo "  Sentiment 后端代码部署"
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
