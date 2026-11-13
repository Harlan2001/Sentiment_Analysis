#!/bin/bash
# Sentiment 定时任务（大前台）：新闻重要性分窗口兜底重算（S3-2）
# 建议执行时间：每天 23:30（分析补偿 23:00 之后，确保当日新分析新闻已落库）
# 用法：./recompute_importance_bigfrontend.sh
# 或在 crontab 中：30 23 * * * /opt/sentiment-tasks/scripts/recompute_importance_bigfrontend.sh
#
# 说明：新闻分析完成时 analyzer_runner 已增量打分，本任务是兜底——
# 重算近 30 天（推荐流最大窗口）新闻，修复增量失败/公式调参后的分值漂移。
# 首次上线的存量全量回算请手动执行一次：
#   docker compose exec -T backend /app/.venv/bin/python -m scripts.recompute_news_importance --all

set -e

# 配置工作目录
# 允许通过环境变量覆盖，便于测试/灰度验证
WORKDIR="${WORKDIR:-/opt/sentiment}"
LOG_FILE="${LOG_FILE:-/opt/sentiment/logs/sentiment-importance.log}"

# 如果 LOG_FILE 目录不存在，创建它；日志文件本身会在首次写入时自动创建
mkdir -p "$(dirname "$LOG_FILE")"

cd "$WORKDIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting news importance recompute (window=30d)..." >> "$LOG_FILE"

# 执行近 30 天窗口重算，upsert 幂等，重复执行不会产生重复行
if docker compose exec -T backend /app/.venv/bin/python -m scripts.recompute_news_importance \
  --window 30 \
  >> "$LOG_FILE" 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] News importance recompute completed successfully." >> "$LOG_FILE"
else
  exit_code=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] News importance recompute failed with exit code $exit_code." >> "$LOG_FILE"
  exit "$exit_code"
fi
