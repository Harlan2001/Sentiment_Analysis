"""
飞书机器人 — 债券市场预测日报推送

流程：生成 PDF → 提取报告摘要 → 发文本消息 → 发 PDF 文件
使用方式：python -m backend.push.test_feishu
"""

from pathlib import Path
import sys
import json
import time
import requests
from typing import Optional, Tuple

# Windows GBK 兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ===================== 配置加载 =====================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import os
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env")
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


def build_summary(pdf_file_name: str) -> str:
    """
    从最新 forecast_report 中提取关键信息，生成报告摘要文本。
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

        # 报告摘要
        summary = pred.get("报告摘要", "")

        # 市场情绪（嵌套字段可能是 JSON 字符串，需要 _safe_get 解析）
        overview = _safe_get(pred, "市场概览", {})
        sentiment = overview.get("市场情绪", "—") if isinstance(overview, dict) else "—"

        # 日/周/月预测
        forecasts = _safe_get(pred, "预测结果", {})
        lines = []
        if isinstance(forecasts, dict):
            for period, label in [("日", "日度"), ("周", "周度"), ("月", "月度")]:
                f = forecasts.get(period, {})
                if isinstance(f, dict):
                    up = f.get("上涨概率", "—")
                    down = f.get("下跌概率", "—")
                    conf = f.get("置信度", "—")
                    lines.append(f"{label}: 涨 {up}% / 跌 {down}%（置信度 {conf}）")
        if not lines:
            lines = ["预测数据暂不可用"]

        # 主要风险
        risks_info = _safe_get(pred, "风险提示", {})
        risks = risks_info.get("主要风险", []) if isinstance(risks_info, dict) else []
        risk_str = "、".join(risks[:3]) if risks else "—"

        return (
            f"📊 {date_str} 债券市场预测报告\n\n"
            f"【市场情绪】{sentiment}\n\n"
            f"{chr(10).join(lines)}\n\n"
            f"【主要风险】{risk_str}\n\n"
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
