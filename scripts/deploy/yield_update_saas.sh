#!/bin/bash
# Sentiment 定时任务（SAAS）：收益率数据更新（先下载最新 Excel，再追加导入）
# 建议执行时间：每天 19:00
# 用法：./yield_update_saas.sh
# 或在 crontab 中：0 19 * * * /data/sentiment-tasks/yield_update_saas.sh

set -e

# 配置工作目录
# 允许通过环境变量覆盖，便于测试/灰度验证
WORKDIR="${WORKDIR:-/data/sentiment}"
LOG_FILE="${LOG_FILE:-/data/sentiment/logs/sentiment-yield.log}"

# 如果 LOG_FILE 目录不存在，创建它；日志文件本身会在首次写入时自动创建
mkdir -p "$(dirname "$LOG_FILE")"

cd "$WORKDIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting yield data update..." >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Download latest Excel and append new yield rows only." >> "$LOG_FILE"

# 执行更新命令：模块内部会先下载最新 Excel，再按 (date, period) 追加导入
if docker compose exec -T backend uv run python -m backend.tools.bond_downloader \
  --excel-path data/GovernmentBonds.xlsx \
  >> "$LOG_FILE" 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Yield data update completed successfully." >> "$LOG_FILE"
else
  exit_code=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Yield data update failed with exit code $exit_code." >> "$LOG_FILE"
  exit "$exit_code"
fi
