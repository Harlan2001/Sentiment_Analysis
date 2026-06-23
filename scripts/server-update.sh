#!/bin/bash
# =============================================================================
# 服务器端更新脚本
# 用法：./scripts/server-update.sh
# 放在服务器 /opt/sentiment/ 目录下执行
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 开始拉取最新镜像 ==="

docker compose pull

echo "=== 重启服务 ==="

docker compose up -d --force-recreate

echo "=== 清理无用镜像 ==="

docker image prune -f

echo "=== 检查服务状态 ==="

docker compose ps

echo ""
echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 更新完成 ==="
