"""
飞书机器人 — 债券市场预测日报推送

流程：生成 PDF → 提取报告摘要 → 发文本消息 → 发 PDF 文件
使用方式：python -m backend.push.test_feishu
"""

from pathlib import Path
import sys
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Windows GBK 兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

# ===================== 配置加载 =====================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import os
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env", override=True)
except ImportError:
    pass

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")
GROUP_ID = os.getenv("FEISHU_GROUP_ID")
GENERATE_PDF_API = os.getenv("GENERATE_PDF_API", "http://127.0.0.1:8000/api/report/generate-prediction")
FORECAST_API = os.getenv("FORECAST_API", "http://127.0.0.1:8000/api/forecast")

# 必填配置校验
for k, v in {"FEISHU_APP_ID": APP_ID, "FEISHU_APP_SECRET": APP_SECRET, "FEISHU_GROUP_ID": GROUP_ID}.items():
    if not v:
        raise RuntimeError(f"缺少必要的环境变量: {k}，请在 .env 文件中配置")

# ===================== PDF 生成 =====================

def generate_latest_pdf() -> Optional[Tuple[str, str]]:
    """调用后端 API 生成最新预测报告 PDF，返回 (file_path, file_name)。"""
    try:
        res = requests.post(GENERATE_PDF_API, timeout=120)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                info = data["data"]
                return info["file_path"], info["file_name"]
        print(f"[PDF] 生成失败: HTTP {res.status_code}")
        return None
    except requests.exceptions.ConnectionError:
        print("[PDF] 无法连接后端服务")
        return None
    except Exception as e:
        print(f"[PDF] 异常: {e}")
        return None

# ===================== 报告摘要 =====================

def _safe_get(pred: dict, key: str, default=None):
    """安全取值：若值为 JSON 字符串则自动解析，解析失败返回默认值。"""
    v = pred.get(key, default)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v if v is not None else default


def _truncate(text: str, max_len: int = 150) -> str:
    """截断文本，尽量在句号处断开。"""
    if not text or not isinstance(text, str):
        return "—"
    if len(text) <= max_len:
        return text
    # 在 max_len 范围内找最后一个句号断开
    cut = text[:max_len].rstrip()
    last_period = max(cut.rfind("。"), cut.rfind("；"), cut.rfind("，"))
    if last_period > max_len // 2:
        return cut[:last_period + 1] + "…"
    return cut + "…"


def build_summary(pdf_file_name: str) -> str:
    """
    从最新 forecast_report 中提取报告摘要，生成简洁推送文本。
    数据来自 AI 已生成的 full_report，无需额外调用模型。
    """
    date_str = pdf_file_name.replace(".pdf", "")

    try:
        resp = requests.get(FORECAST_API, params={"date": date_str}, timeout=30)
        if resp.status_code != 200:
            return f"📊 {date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

        data = resp.json()
        reports = data.get("reports", [])
        full_report = next((r for r in reports if r.get("forecast_type") == "full_report"), None)
        if not full_report:
            return f"📊 {date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

        pred = full_report.get("prediction", {})
        if not isinstance(pred, dict):
            return f"📊 {date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

        # 报告摘要（LLM 已生成的结论性摘要文本）
        summary = _safe_get(pred, "报告摘要", "")
        summary_str = str(summary).strip() if summary else "—"

        return (
            f"📊 {date_str} 债券市场预测报告\n\n"
            f"【报告摘要】\n{summary_str}\n\n"
            f"📄 完整分析请查看下方 PDF"
        )
    except Exception as e:
        print(f"[摘要] 生成失败: {e}")
        return f"📊 {date_str} 债券市场预测报告\n\n📄 完整分析请查看下方 PDF"

# ===================== 飞书 API =====================

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_IM_FILES_URL = "https://open.feishu.cn/open-apis/im/v1/files"
FEISHU_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
FEISHU_DRIVE_URL = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"


def get_tenant_token() -> Optional[str]:
    """获取飞书 tenant_access_token。"""
    try:
        resp = requests.post(FEISHU_TOKEN_URL, json={
            "app_id": APP_ID, "app_secret": APP_SECRET
        }, timeout=10)
        result = resp.json()
        if result.get("code") == 0:
            return result["tenant_access_token"]
        print(f"[Token] 获取失败: {result}")
        return None
    except Exception as e:
        print(f"[Token] 异常: {e}")
        return None


def upload_pdf_to_im(token: str, pdf_path: str) -> Optional[str]:
    """
    上传 PDF 到飞书 IM（用于文件消息发送）。
    使用 im/v1/files 接口，返回的 file_key 可直接嵌入消息。
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists() or pdf_file.suffix.lower() != ".pdf":
        print(f"[上传] 文件无效: {pdf_path}")
        return None

    try:
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                FEISHU_IM_FILES_URL,
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (pdf_file.name, f, "application/pdf")},
                data={"file_name": pdf_file.name, "file_type": "pdf"},
                timeout=120,
            )
        res = resp.json()
        file_key = res.get("data", {}).get("file_key") if res.get("code") == 0 else None
        if file_key:
            return file_key
        print(f"[上传] 失败: {res}")
        return None
    except Exception as e:
        print(f"[上传] 异常: {e}")
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
        )
        ok = resp.json().get("code") == 0
        if not ok:
            print(f"[消息] 文本发送失败: {resp.text}")
        return ok
    except Exception as e:
        print(f"[消息] 文本发送异常: {e}")
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
        )
        ok = resp.json().get("code") == 0
        if not ok:
            print(f"[消息] 文件发送失败: {resp.text}")
        return ok
    except Exception as e:
        print(f"[消息] 文件发送异常: {e}")
        return False

# ===================== 主流程 =====================

def main():
    # 1. 生成 PDF
    result = generate_latest_pdf()
    if not result:
        print("[主流程] PDF 生成失败，终止")
        return
    pdf_path, pdf_name = result

    # 日期校验：仅当前一日报告才推送
    report_date_str = pdf_name.replace(".pdf", "")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if report_date_str != yesterday_str:
        logger.info("报告日期校验未通过，当前最新报告日期: %s，期望日期: %s，跳过推送", report_date_str, yesterday_str)
        return

    # 2. 获取 Token
    token = get_tenant_token()
    if not token:
        print("[主流程] Token 获取失败，终止")
        return

    # 3. 上传 PDF 到飞书 IM
    file_key = upload_pdf_to_im(token, pdf_path)
    if not file_key:
        print("[主流程] 文件上传失败，终止")
        return

    # 4. 发送报告摘要文本
    summary = build_summary(pdf_name)
    send_text(token, GROUP_ID, summary)

    # 5. 短暂延迟后发送 PDF 文件（等待飞书文件处理完成）
    time.sleep(2)
    send_file(token, GROUP_ID, file_key)

    print(f"[主流程] 推送完成: {pdf_name}")

if __name__ == "__main__":
    main()
