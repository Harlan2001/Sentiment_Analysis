#!/bin/bash
# Sentiment 定时任务（SAAS）：生成昨日交易日报告 + 飞书推送
# 建议执行时间：每天 09:00
# 用法：./report_push_saas.sh
# 或在 crontab 中：0 9 * * * /data/sentiment-tasks/report_push_saas.sh

# 配置工作目录
# 允许通过环境变量覆盖，便于测试/灰度验证
WORKDIR="${WORKDIR:-/data/sentiment}"
LOG_FILE="${LOG_FILE:-/data/sentiment/logs/sentiment-report.log}"

# 如果 LOG_FILE 目录不存在，创建它；日志文件本身会在首次写入时自动创建
mkdir -p "$(dirname "$LOG_FILE")"

cd "$WORKDIR" || exit 1

# 计算昨日交易日
# 注意：在 macOS 上使用 date -v-1d，在 Linux 上使用 date -d "yesterday"
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  YESTERDAY=$(date -v-1d +%Y-%m-%d)
else
  # Linux
  YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting report generation for trade date: $YESTERDAY" >> "$LOG_FILE"

# 执行报告生成命令
docker compose exec -T backend uv run python -m backend.analysis.generate_report \
  --start-date "$YESTERDAY" \
  --end-date "$YESTERDAY" \
  >> "$LOG_FILE" 2>&1

exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Report generation completed successfully for $YESTERDAY." >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Report generation failed with exit code $exit_code for $YESTERDAY." >> "$LOG_FILE"
  exit 1
fi

# ========== PDF 生成 + 飞书推送 ==========

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting PDF generation and Feishu push for $YESTERDAY." >> "$LOG_FILE"

docker compose exec -T backend uv run python -m backend.push.feishu_daily_push \
  >> "$LOG_FILE" 2>&1

push_exit_code=$?

if [ $push_exit_code -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] PDF generation and Feishu push completed successfully for $YESTERDAY." >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] PDF generation or Feishu push failed with exit code $push_exit_code for $YESTERDAY." >> "$LOG_FILE"
  exit 1
fi
