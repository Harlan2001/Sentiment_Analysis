"""政策文件解析：从 PDF 提取标题、发文机关、文号、发布日期与全文。

与研报解析（research_report/parser.py）同属 PDF 解析，但**提取目标不同**：
研报取"机构/行业/观点"，政策文件取"发文机关/文号/发布日期"。

**仅支持 PDF**（用户已确认不做 Word —— 那需要引入 python-docx 依赖）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

# 全文过短时给出告警（可能是扫描件，未识别到文本）
MIN_TEXT_LENGTH = 50

# 中文政策文件常见的发文机关（用于从正文首部识别）
_ISSUER_PATTERNS = [
    r"(国务院办公厅)",
    r"(国务院)",
    r"(中国人民银行|人民银行|央行)",
    r"(财政部)",
    r"(国家发展和改革委员会|发展改革委|发改委)",
    r"(中国证券监督管理委员会|证监会)",
    r"(国家金融监督管理总局|金融监管总局|银保监会|银监会)",
    r"(国家外汇管理局|外汇局)",
    r"(商务部)",
    r"(工业和信息化部|工信部)",
    r"(住房和城乡建设部|住建部)",
    r"(国家税务总局|税务总局)",
    r"([一-龥]{2,12}(?:部|委|署|局|厅|办公室|银行))",
]

# 文号：如 银发〔2026〕1号 / 国办发〔2026〕12号 / 财税〔2026〕1号
_DOC_NO_RE = re.compile(
    r"[一-龥]{1,10}[〔\[（(]\s*(\d{4})\s*[〕\]）)]\s*第?\s*(\d+)\s*号"
)

# 中文发布日期：2026年10月20日 / 2026-10-20
_CN_DATE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


@dataclass
class PolicyDocumentData:
    """解析结果。"""

    title: str = ""
    issuer: str | None = None
    document_no: str | None = None
    publish_date: date | None = None
    full_text: str = ""
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    """压缩多余空白，保留段落换行。"""
    text = text.replace("　", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _detect_issuer(text: str) -> str | None:
    """从正文首部识别发文机关。

    只看前 500 字 —— 发文机关在文件头部，正文后段提及的机关不具代表性。
    """
    head = text[:500]
    for pattern in _ISSUER_PATTERNS:
        match = re.search(pattern, head)
        if match:
            return match.group(1)
    return None


def _detect_document_no(text: str) -> str | None:
    """识别文号（取正文中首个匹配，文号通常在头部）。"""
    match = _DOC_NO_RE.search(text[:800])
    return match.group(0).strip() if match else None


def _detect_publish_date(text: str) -> date | None:
    """识别发布日期；支持中文日期与 ISO 格式。"""
    head = text[:1200]
    match = _CN_DATE_RE.search(head) or _ISO_DATE_RE.search(head)
    if not match:
        return None
    try:
        year, month, day = (int(match.group(i)) for i in (1, 2, 3))
        return date(year, month, day)
    except ValueError:
        return None


def _detect_title(text: str, fallback: str) -> str:
    """识别标题：取正文首个非空且长度合适的行。

    政策文件标题通常位于首行且不含正文标点（如"："结尾的引导句）。
    """
    for raw_line in text.split("\n")[:12]:
        line = raw_line.strip()
        if not line:
            continue
        # 标题一般 6-60 字，且不以冒号/句号结尾（那些是正文引导句）
        if 6 <= len(line) <= 60 and not line.endswith(("：", ":", "。", "；")):
            return line
    return fallback


def parse_policy_pdf(pdf_path: Path, fallback_title: str = "") -> PolicyDocumentData:
    """解析政策文件 PDF。

    解析失败抛 RuntimeError；文本过短只告警不失败（可能是扫描件）。
    """
    result = PolicyDocumentData()

    try:
        document = pymupdf.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"PDF 打开失败: {exc}") from exc

    try:
        result.page_count = document.page_count
        pages_text = []
        for page in document:
            pages_text.append(page.get_text())
        raw_text = "\n".join(pages_text)
    finally:
        document.close()

    result.full_text = _clean(raw_text)

    if len(result.full_text) < MIN_TEXT_LENGTH:
        # 扫描件/图片型 PDF：明确告警，不静默当作成功
        result.warnings.append(
            f"解析到的文本过短（{len(result.full_text)} 字），可能为扫描件或图片型 PDF"
        )
        result.title = fallback_title or "未识别标题"
        return result

    result.title = _detect_title(result.full_text, fallback_title or "未识别标题")
    result.issuer = _detect_issuer(result.full_text)
    result.document_no = _detect_document_no(result.full_text)
    result.publish_date = _detect_publish_date(result.full_text)

    return result