#!/bin/bash
# Sentiment 定时任务（SAAS）：分析补偿任务（兜底处理）
# 建议执行时间：每天 23:00
# 用法：./analysis_fallback_saas.sh
# 或在 crontab 中：0 23 * * * /data/sentiment-tasks/analysis_fallback_saas.sh

set -e

# 配置工作目录
# 允许通过环境变量覆盖，便于测试/灰度验证
WORKDIR="${WORKDIR:-/data/sentiment_deploy}"
LOG_FILE="${LOG_FILE:-/data/sentiment_deploy/logs/sentiment-fallback.log}"

# 如果 LOG_FILE 目录不存在，创建它；日志文件本身会在首次写入时自动创建
mkdir -p "$(dirname "$LOG_FILE")"

cd "$WORKDIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting analysis fallback compensation task..." >> "$LOG_FILE"

# 执行兜底补偿任务
# mode=model_missing：处理那些未被任何模型分析过的新闻
# limit=1000：单次最多处理 1000 条新闻
docker compose exec -T backend uv run python -m backend.analysis.analyzer_runner \
  --mode model_missing \
  --limit 1000 \
  >> "$LOG_FILE" 2>&1

exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Analysis fallback compensation completed successfully." >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Analysis fallback compensation failed with exit code $exit_code." >> "$LOG_FILE"
  exit 1
fi
