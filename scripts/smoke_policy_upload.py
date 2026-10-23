"""端到端验证：生成一份模拟政策文件 PDF 并走完整上传→解析链路。

该脚本仅用于开发期验证，不参与生产逻辑。
"""

from __future__ import annotations

import io

import pymupdf
import requests

PDF_PATH = ".tmp/test_policy.pdf"


def build_pdf() -> bytes:
    """构造一份带发文机关/文号/日期的中文政策文件 PDF。"""
    document = pymupdf.open()
    page = document.new_page()
    # 用内置中文字体写入（pymupdf 自带 CJK 支持）
    lines = [
        ("中国人民银行", 90, 16),
        ("银发〔2026〕15号", 115, 12),
        ("关于下调金融机构存款准备金率的通知", 150, 15),
        ("", 175, 12),
        ("中国人民银行决定于2026年10月20日起，下调金融机构", 205, 11),
        ("存款准备金率0.5个百分点，本次下调后金融机构加权平均", 225, 11),
        ("存款准备金率约为6.6%。此举旨在保持流动性合理充裕，", 245, 11),
        ("降低金融机构资金成本，支持实体经济发展。", 265, 11),
        ("", 285, 11),
        ("本次降准将释放长期资金约1万亿元，有助于引导市场", 305, 11),
        ("利率下行，降低实体经济融资成本。", 325, 11),
        ("", 345, 11),
        ("中国人民银行", 375, 11),
        ("2026年10月20日", 395, 11),
    ]
    for text, y, size in lines:
        if text:
            page.insert_text((72, y), text, fontname="china-s", fontsize=size)
    data = document.tobytes()
    document.close()
    return data


def main() -> None:
    with open(PDF_PATH, "wb") as handle:
        handle.write(build_pdf())
    print(f"已生成测试 PDF: {PDF_PATH}")

    with open(PDF_PATH, "rb") as handle:
        response = requests.post(
            "http://127.0.0.1:8000/sapi/policy-documents/upload",
            files={"file": ("test_policy.pdf", handle, "application/pdf")},
            timeout=120,
        )
    print("上传状态码:", response.status_code)
    payload = response.json()
    data = payload.get("data", payload)
    print("解析结果:")
    for key in ("document_id", "title", "issuer", "document_no", "publish_date", "page_count", "is_duplicate", "warnings"):
        print(f"  {key}: {data.get(key)}")
    print("\n注意：分析在服务端后台线程执行，可用以下命令查状态：")
    print(f"  curl http://127.0.0.1:8000/sapi/policy-documents/{data.get('document_id')}")


if __name__ == "__main__":
    main()