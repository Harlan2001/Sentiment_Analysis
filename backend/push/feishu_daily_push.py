"""
飞书机器人 — 债券市场预测日报推送

流程：生成 PDF → 提取报告摘要 → 发文本消息 → 发 PDF 文件
使用方式：python -m backend.push.feishu_daily_push
"""

import json
import os
import sys
import logging
import requests
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from backend.common.database import get_db_connection, init_database, DatabaseConfig
from backend.config.config import MYSQL_CONFIG, get_requests_proxies
from backend.push.pdf_generator import generate_prediction_pdf

# ===================== 配置 =====================

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")
GROUP_ID = os.getenv("FEISHU_GROUP_ID")

for k, v in {"FEISHU_APP_ID": APP_ID, "FEISHU_APP_SECRET": APP_SECRET, "FEISHU_GROUP_ID": GROUP_ID}.items():
    if not v:
        raise RuntimeError(f"缺少必要的环境变量: {k}，请在 .env 文件中配置")

# ===================== PDF 生成 =====================


def generate_latest_pdf() -> Optional[Tuple[str, str]]:
    """查询最新报告日期，直接调用 pdf_generator 生成 PDF，返回 (file_path, file_name)。"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MAX(trade_date) FROM forecast_report")
            row = cur.fetchone()
            if not row or not row[0]:
                logger.error("[PDF] forecast_report 表为空")
                return None
            report_date = row[0] if isinstance(row[0], date) else row[0]

        pdf_path, _actual_trade_date = generate_prediction_pdf(report_date=report_date)
        return str(pdf_path), os.path.basename(pdf_path)
    except Exception as e:
        logger.error("[PDF] 生成失败: %s", e, exc_info=True)
        return None


# ===================== 报告摘要 =====================


def _safe_get(pred: dict, key: str, default=None):
    """安全取值：若值为 JSON 字符串则自动解析。"""
    v = pred.get(key, default)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v if v is not None else default


def build_summary(pdf_file_name: str) -> str:
    """从 forecast_report 表中提取报告摘要，生成推送文本。"""
    date_str = pdf_file_name.replace(".pdf", "")
    fallback = f"📊 {date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT prediction FROM forecast_report WHERE trade_date = %s AND forecast_type = 'full_report'",
                (date_str,),
            )
            row = cur.fetchone()
            if not row:
                return fallback

            pred = row[0]
            if isinstance(pred, str):
                pred = json.loads(pred)
            if not isinstance(pred, dict):
                return fallback

            summary = _safe_get(pred, "报告摘要", "")
            summary_str = str(summary).strip() if summary else "—"

            return (
                f"📊 {date_str} 债券市场预测报告\n\n"
                f"【报告摘要】\n{summary_str}\n\n"
                f"📄 完整分析请查看下方 PDF"
            )
    except Exception as e:
        logger.warning("[摘要] 生成失败: %s", e)
        return fallback


# ===================== 飞书 API =====================

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_IM_FILES_URL = "https://open.feishu.cn/open-apis/im/v1/files"
FEISHU_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


def get_tenant_token() -> Optional[str]:
    """获取飞书 tenant_access_token。"""
    try:
        resp = requests.post(FEISHU_TOKEN_URL, json={
            "app_id": APP_ID, "app_secret": APP_SECRET
        }, timeout=10, proxies=get_requests_proxies())
        result = resp.json()
        if result.get("code") == 0:
            return result["tenant_access_token"]
        logger.error("[Token] 获取失败: %s", result)
        return None
    except Exception as e:
        logger.error("[Token] 异常: %s", e, exc_info=True)
        return None


def upload_pdf_to_im(token: str, pdf_path: str) -> Optional[str]:
    """上传 PDF 到飞书 IM，返回 file_key。"""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists() or pdf_file.suffix.lower() != ".pdf":
        logger.error("[上传] 文件无效: %s", pdf_path)
        return None

    try:
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                FEISHU_IM_FILES_URL,
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (pdf_file.name, f, "application/pdf")},
                data={"file_name": pdf_file.name, "file_type": "pdf"},
                timeout=120,
                proxies=get_requests_proxies(),
            )
        res = resp.json()
        file_key = res.get("data", {}).get("file_key") if res.get("code") == 0 else None
        if file_key:
            return file_key
        logger.error("[上传] 失败: %s", res)
        return None
    except Exception as e:
        logger.error("[上传] 异常: %s", e, exc_info=True)
        return None


def send_text(token: str, chat_id: str, text: str) -> bool:
    """发送文本消息到飞书群。"""
    try:
        resp = requests.post(
            FEISHU_MSG_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"receive_id_type": "chat_id"},
            json={"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": text})},
            timeout=30,
            proxies=get_requests_proxies(),
        )
        ok = resp.json().get("code") == 0
        if not ok:
            logger.warning("[消息] 文本发送失败: %s", resp.text[:200])
        return ok
    except Exception as e:
        logger.error("[消息] 文本发送异常: %s", e, exc_info=True)
        return False


def send_file(token: str, chat_id: str, file_key: str) -> bool:
    """发送 PDF 文件消息到飞书群。"""
    try:
        resp = requests.post(
            FEISHU_MSG_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": "file",
                "content": json.dumps({"file_key": file_key}),
            },
            timeout=30,
            proxies=get_requests_proxies(),
        )
        ok = resp.json().get("code") == 0
        if not ok:
            logger.warning("[消息] 文件发送失败: %s", resp.text[:200])
        return ok
    except Exception as e:
        logger.error("[消息] 文件发送异常: %s", e, exc_info=True)
        return False


# ===================== 主流程 =====================


def main():
    # 0. 初始化数据库连接
    init_database(DatabaseConfig(**MYSQL_CONFIG))

    # 1. 生成 PDF
    result = generate_latest_pdf()
    if not result:
        logger.error("[主流程] PDF 生成失败，终止")
        sys.exit(1)
    pdf_path, pdf_name = result

    # 日期校验：仅前一日报告才推送
    report_date_str = pdf_name.replace(".pdf", "")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if report_date_str != yesterday_str:
        logger.info("报告日期校验未通过，当前最新报告日期: %s，期望日期: %s，跳过推送", report_date_str, yesterday_str)
        return

    # 2. 获取 Token
    token = get_tenant_token()
    if not token:
        logger.error("[主流程] Token 获取失败，终止")
        sys.exit(1)

    # 3. 上传 PDF 到飞书 IM
    file_key = upload_pdf_to_im(token, pdf_path)
    if not file_key:
        logger.error("[主流程] 文件上传失败，终止")
        sys.exit(1)

    # 4. 发送报告摘要文本
    summary = build_summary(pdf_name)
    send_text(token, GROUP_ID, summary)

    # 5. 发送 PDF 文件
    send_file(token, GROUP_ID, file_key)

    logger.info("[主流程] 推送完成: %s", pdf_name)


if __name__ == "__main__":
    from backend.common.logging_config import setup_logging
    setup_logging()
    main()
