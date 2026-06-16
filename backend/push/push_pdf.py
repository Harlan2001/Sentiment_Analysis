"""
飞书机器人 PDF 推送

功能：
1. 自动获取本机内网 IP，调用后端 API 生成最新预测报告 PDF
2. 推送文字 + PDF 下载链接到飞书群机器人

使用方式：
    python backend/push_pdf.py

配置（.env）：
    FEISHU_WEBHOOK         - 飞书机器人 Webhook 地址
    SERVER_BASE_URL        - 后端服务公网地址（可选，留空自动检测内网 IP）
    FRONTEND_BASE_URL      - 前端地址（默认 http://localhost:5173）

定时任务：
    配合 backend/scheduler.py 实现每天 10:00 自动执行
"""

import os
import re
import sys
import socket
import requests
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


# ====================== IP 自动检测 ======================

def _get_local_ip() -> str:
    """自动获取本机内网 IPv4 地址（同 Vite 的 getLocalIp 逻辑）。"""
    # 方法1：UDP socket 路由表探测
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.253.0.0", 1))
            return s.getsockname()[0]
    except Exception:
        pass

    # 方法2：遍历所有网卡接口
    try:
        import netifaces
        for iface_name in netifaces.interfaces():
            for addr in netifaces.ifaddresses(iface_name).get(netifaces.AF_INET, []):
                ip = addr.get("addr", "")
                if ip and not ip.startswith("127."):
                    return ip
    except Exception:
        pass

    return "127.0.0.1"


LOCAL_IP = _get_local_ip()


# ====================== 配置（全部来自 .env） ======================

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").rstrip("/") or \
    f"http://{LOCAL_IP}:8000"

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")

GENERATE_PDF_API = "http://127.0.0.1:8000/api/pdf/generate-prediction"
PDF_DIR = BASE_DIR / "data" / "pdf"


# ====================== 核心函数 ======================


def generate_latest_pdf() -> tuple[str, str] | None:
    """
    调用后端 API 生成最新的预测报告 PDF。

    后端会通过 Playwright 访问前端页面，自动展示最近的预测数据，
    并从页面提取实际 trade_date 作为 PDF 文件名。

    Returns:
        (file_path, file_name) 如果成功，None 如果失败
    """
    try:
        print(f"[PDF生成] 本机 IP: {LOCAL_IP}")
        print(f"[PDF生成] 正在通过前端生成最新预测报告...")
        res = requests.get(GENERATE_PDF_API, timeout=120)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                info = data["data"]
                file_path = info["file_path"]
                file_name = info["file_name"]
                file_size = info["file_size_bytes"] / 1024
                print(f"[PDF生成] ✅ {file_name} ({file_size:.1f} KB)")
                return file_path, file_name
            else:
                print(f"[PDF生成] ❌ 失败: {data}")
                return None
        else:
            print(f"[PDF生成] ❌ HTTP {res.status_code}: {res.text[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"[PDF生成] ❌ 无法连接后端服务，请确保 main.py 已启动")
        return None
    except Exception as e:
        print(f"[PDF生成] ❌ 异常: {e}")
        return None


def push_to_feishu(file_name: str) -> bool:
    """
    推送文字 + PDF 下载链接到飞书群机器人。

    从文件名提取报告日期用于消息展示。
    """
    if not FEISHU_WEBHOOK:
        print("[飞书推送] ❌ 未配置 FEISHU_WEBHOOK，请在 .env 中设置")
        return False

    match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
    date_str = match.group(1) if match else datetime.now().strftime("%Y-%m-%d")

    pdf_url = f"{SERVER_BASE_URL}/api/pdf/files/{file_name}"
    msg = f"📊 {date_str} 债券市场预测报告已生成\n\n📄 查看报告: {pdf_url}"

    print(f"[飞书推送] SERVER_BASE_URL: {SERVER_BASE_URL}")
    print(f"[飞书推送] PDF 链接: {pdf_url}")

    try:
        res = requests.post(
            FEISHU_WEBHOOK,
            json={"msg_type": "text", "content": {"text": msg}},
            timeout=30,
        )
        result = res.json()
        if result.get("code") == 0:
            print(f"[飞书推送] ✅ 已推送到群聊")
            return True
        else:
            print(f"[飞书推送] ❌ 失败: {result}")
            return False
    except Exception as e:
        print(f"[飞书推送] ❌ 异常: {e}")
        return False


# ====================== 入口 ======================

if __name__ == "__main__":
    print("=" * 60)
    print(f"  飞书 PDF 推送")
    print(f"  本机 IP: {LOCAL_IP}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    result = generate_latest_pdf()
    if not result:
        print("\n[错误] PDF 生成失败，推送终止")
        sys.exit(1)

    file_path, file_name = result
    success = push_to_feishu(file_name)

    print()
    if success:
        print(f"✅ 完成: {file_name} 已推送到飞书")
    else:
        print(f"❌ 失败: 推送未成功")
        sys.exit(1)
