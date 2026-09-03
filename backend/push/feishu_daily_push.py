"""
飞书机器人 — 债券市场预测日报推送

流程：生成 PDF → 提取报告摘要 → 发文本消息 → 发 PDF 文件
使用方式：python -m backend.push.feishu_daily_push
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from backend.integrations.feishu.client import FeishuApiError, FeishuClient
from backend.push.pdf_generator import generate_prediction_pdf
from backend.repositories.forecast_report_repository import ForecastReportRepository

logger = logging.getLogger(__name__)

# ===================== 配置 =====================

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")
GROUP_ID = os.getenv("FEISHU_GROUP_ID")


def _require_env() -> None:
    """校验必需环境变量（延迟到 main 调用，保持模块可导入 / 可单测）。"""
    for k, v in {
        "FEISHU_APP_ID": APP_ID,
        "FEISHU_APP_SECRET": APP_SECRET,
        "FEISHU_GROUP_ID": GROUP_ID,
    }.items():
        if not v:
            raise RuntimeError(f"缺少必要的环境变量: {k}，请在 .env 文件中配置")


# ===================== PDF 生成 =====================


def generate_latest_pdf(
    repo: Optional[ForecastReportRepository] = None,
) -> Optional[Tuple[str, str]]:
    """查询最新报告日期并生成 PDF，返回 (file_path, trade_date_str)；无可报告时返回 None。"""
    try:
        repo = repo or ForecastReportRepository()
        report_date = repo.get_latest_trade_date()
        if report_date is None:
            logger.error("[PDF] forecast_report 表为空")
            return None

        pdf_path, trade_date_str = generate_prediction_pdf(report_date=report_date)
        return str(pdf_path), trade_date_str
    except Exception as e:
        logger.error("[PDF] 生成失败: %s", e, exc_info=True)
        return None


# ===================== 报告摘要 =====================


def _summary_text(pred: dict) -> str:
    """提取报告摘要字段；兼容嵌套 JSON 字符串（解析后取文本）。"""
    value = pred.get("报告摘要")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    summary = value if value is not None else ""
    return str(summary).strip() if summary else "—"


def build_summary(trade_date_str: str, repo: Optional[ForecastReportRepository] = None) -> str:
    """从 forecast_report 表中提取报告摘要，生成推送文本。"""
    fallback = f"📊 {trade_date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

    try:
        repo = repo or ForecastReportRepository()
        pred = repo.get_prediction(trade_date_str)
        if pred is None:
            return fallback

        summary_str = _summary_text(pred)
        return (
            f"📊 {trade_date_str} 债券市场预测报告\n\n"
            f"【报告摘要】\n{summary_str}\n\n"
            f"📄 完整分析请查看下方 PDF"
        )
    except Exception as e:
        logger.warning("[摘要] 生成失败: %s", e)
        return fallback


# ===================== 主流程 =====================


def main() -> None:
    # 0. 校验环境变量
    _require_env()

    # 1. 生成 PDF
    result = generate_latest_pdf()
    if not result:
        logger.error("[主流程] PDF 生成失败，终止")
        sys.exit(1)
    pdf_path, trade_date_str = result

    # 日期校验：仅前一日报告才推送（报告日期按 Asia/Shanghai 生成，避免容器 UTC 时区差一天）
    yesterday_str = (datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )
    if trade_date_str != yesterday_str:
        logger.info(
            "报告日期校验未通过，当前最新报告日期: %s，期望日期: %s，跳过推送",
            trade_date_str,
            yesterday_str,
        )
        return

    # 2. 上传 PDF 并发送文本 + 文件到飞书群
    client = FeishuClient()
    try:
        token = client.tenant_access_token()
        file_key = client.upload_file(token, pdf_path)

        summary = build_summary(trade_date_str)
        client.send_text(token, GROUP_ID, summary)
        client.send_file(token, GROUP_ID, file_key)
    except FeishuApiError as e:
        logger.error("[主流程] 飞书推送失败: %s", e)
        sys.exit(1)

    logger.info("[主流程] 推送完成: %s", trade_date_str)


if __name__ == "__main__":
    from backend.common.logging_config import setup_logging

    setup_logging()
    main()
