"""
研报PDF解析器
===========
- 提取元数据（标题、机构、日期、行业、分析师、标的）
- 提取全文文字 + 前端展示清洗版
- 提取内嵌图片（光栅图 + 矢量图区域渲染 + 整页渲染）
- 纯解析函数，不执行文件系统 IO（图片写入由调用方处理）
"""
import hashlib
import logging
import re
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import fitz

from backend.config.config import BASE_DIR
from backend.research_report.constants import (
    KNOWN_INSTITUTIONS, INST_ALIAS_MAP, INST_SHORT_MAP,
    INDUSTRY_KEYWORDS, FIGURE_MIN_BYTES, FIGURE_MAX_PER_REPORT,
)

logger = logging.getLogger(__name__)

# ========================================================================
# 预编译正则 — 消除循环内重复编译
# ========================================================================

_RE_DISPLAY_SKIP = re.compile(
    r"^(?:"
    r"(?:请务必阅读|敬请参阅).*(?:免责|声明)"
    r"|研究所$"
    r"|\d+\s*/\s*\d+$"
    r"|.*分析师[：:]"
    r"|执业证书"
    r"|联系人[：:]"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
    r"|[A-Za-z0-9._%+-]+＠[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
    r"|[a-z]{3,12}$"
    r"|＠[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
    r"|S\d{9,}$"
    r"|扫码"
    r"|行业走势$"
    r"|相关研究$"
    r"|投资评级"
    r"|盈利预测"
    r"|市场数据$"
    r"|基础数据$"
    r"|股价走势$"
    r"|收盘价"
    r"|一年最低"
    r"|市净率"
    r"|流通A股"
    r"|总市值"
    r"|每股净资产"
    r"|资产负债率"
    r"|总股本"
    r"|内容目录$|图表目录$"
    r"|\d+[\.\、\s].*\.{3,}"
    r"|图\d+[：:]"
    r"|表\d+[：:]"
    r"|[─━\-]+$"
    r"|\s*[-+]*\s*\d+\.?\d*%\s*$"
    r"|(?:增持|买入|中性|减持|卖出|强于大市|弱于大市|跑赢|跑输)\s*[（(].*[）)]$"
    r"|（注：.*）$"
    r"|行业.*(?:周报|深度|研究|跟踪)$|公司.*(?:点评|深度)$"
    r"|[\-+]?\d+\.?\d*%\s+[\-+]?\d+\.?\d*%"
    r")"
)

_RE_DISPLAY_SKIP2 = re.compile(
    r"^(?:"
    r"\d+年\d"
    r"|\d{2,4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}\s+"
    r"|\d{4}[A-Z]\s+\d{4}[A-Z]"
    r"|金属材料组$"
    r"|[一-鿿]{2,6}[组部处室]$"
    r")"
)

_RE_STOP = re.compile(
    r"^(?:"
    r"(?:内容|图表|图|表)\s*目录\s*$"
    r"|[一二三四五六七八九十]、\s*\S.*\.{3,}"
    r"|\d+[\.\、\s]\s*\S.*\.{3,}"
    r"|◼?\s*风险提示[：:]"
    r")"
)

_RE_SECTION_HEADER = re.compile(
    r"^(?:[一二三四五六七八九十]+[、．.]|(?:\d+[\.\、])\s*\S|◼\s*)"
)

_RE_TITLE_SKIP = re.compile(
    r"^(?:"
    r"证券研究报告|研究所|\d+\s*/\s*\d+$"
    r"|请务必阅读.*免责|敬请参阅.*声明"
    r"|[（(]\d{6}[）)]$"
    r"|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日$"
    r"|证券分析师|执业证书|联系人[：:]"
    r"|[A-Za-z0-9._%+-]+[@＠][A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
    r"|[A-Z]{2}\d{6}|S\d{9,}|[a-z]{3,12}$"
    r"|扫码|行业走势|相关研究|投资评级|盈利预测"
    r"|市场数据|基础数据|股价走势"
    r"|收盘价|一年最低|市净率|流通A股|总市值|每股净资产|资产负债率|总股本"
    r"|^[\d]{2,4}[年/\.\-]"
    r"|^[-+]*\s*\d+\.?\d*"
    r"|^[A-Z].*"
    r")"
)

# 补充检查：行中包含研究所关键词也应过滤（不在^(?:...)锚定内）
_RE_TITLE_SKIP2 = re.compile(r"研究所")

_RE_DATE_YMD = re.compile(r"-(\d{2})(\d{2})(\d{2})(?=[\.\-]|$)")
_RE_DATE_FULL = re.compile(r"-(\d{4})(\d{2})(\d{2})(?=[\.\-]|$)")
_RE_DATE_CN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")

_RE_SYMBOL_DOT = re.compile(r"(\d{6})\.(SH|SZ)", re.IGNORECASE)
_RE_SYMBOL_SH = re.compile(r"([Ss][Hh]\d{6})|([Ss][Zz]\d{6})")
_RE_SYMBOL_BRACKET = re.compile(r"（(\d{6})）")

_RE_ANALYST1 = re.compile(r"证券分析师\s+([^\s（(]{2,4})")
_RE_ANALYST2 = re.compile(r"分析师[：:]\s*([^\s（(]{2,4})")

_RE_FIGURE_CAPTION = re.compile(r'(?:图|图表|Figure|Fig\.?)\s*\d+[：:]\s*(.+?)(?:\n|$)')
_RE_CHART_CAPTION = re.compile(r'(?:图|图表|Figure)\s*\d+[：:]')

_RE_HASH = re.compile(r"^[a-f0-9]{12,16}$")
_RE_IDX_PREFIX = re.compile(r"^\d{1,3}-")
_RE_PDF_EXT = re.compile(r"\.pdf$", re.IGNORECASE)

# 常量
_DPI_RENDER = 150
_MERGE_MARGIN = 20
_MIN_TITLE_CJK = 6
_MIN_DISPLAY_LINE = 4
_DISPLAY_MAX_CHARS = 2500
_VECTOR_MIN_BYTES = 5000
_PAGE_RENDER_MIN_BYTES = 20000
_DRAWING_THRESHOLD = 30
_BRACKET_INST = re.compile(r"【(.+?)】")


# ========================================================================
# 工具函数
# ========================================================================

def compute_file_hash(pdf_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _is_table_row(line: str) -> bool:
    n = len(line)
    if n == 0:
        return True
    return sum(1 for c in line if c.isdigit() or c in '.-/%% \t') / n > 0.55


def _cjk_count(s: str) -> int:
    return sum(1 for c in s if '一' <= c <= '鿿')


# ========================================================================
# 文本清洗
# ========================================================================

def clean_display_text(full_text: str, max_chars: int = _DISPLAY_MAX_CHARS) -> str:
    """清洗研报正文用于前端展示：去页眉页脚，截断到摘要结束位置"""
    cleaned = []
    for line in full_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if _RE_STOP.search(stripped):
            break
        if len(stripped) < _MIN_DISPLAY_LINE:
            continue
        if _RE_DISPLAY_SKIP.search(stripped) or _RE_DISPLAY_SKIP2.search(stripped):
            continue
        if _is_table_row(stripped):
            continue
        cleaned.append(stripped)

    paragraphs = []
    buf = []
    for line in cleaned:
        if line == "":
            if buf:
                paragraphs.append(" ".join(buf))
                buf = []
        elif _RE_SECTION_HEADER.match(line):
            if buf:
                paragraphs.append(" ".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        paragraphs.append(" ".join(buf))

    text = "\n\n".join(paragraphs)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n\n", 1)[0] + "\n\n…"
    return text


# ========================================================================
# 标题/元数据解析
# ========================================================================

def _extract_title(raw_title: str, filename: str) -> str:
    title = raw_title.strip()
    if _RE_HASH.match(title):
        title = filename
    title = _RE_PDF_EXT.sub("", title)
    title = _RE_IDX_PREFIX.sub("", title)
    return title[:512]


def _extract_title_from_text(text: str) -> str | None:
    candidates = []
    for line in text.split("\n")[:30]:
        line = line.strip()
        if not line or len(line) < 6:
            continue
        if _RE_TITLE_SKIP.search(line) or _RE_TITLE_SKIP2.search(line):
            continue
        if _cjk_count(line) >= _MIN_TITLE_CJK and len(line) <= 100:
            candidates.append(line)
    if not candidates:
        return None
    main = candidates[0]
    if len(candidates) > 1 and 20 <= len(candidates[1]) <= 80 and len(main) <= 40:
        main = f"{main}：{candidates[1]}"
    return main[:256]


def _parse_metadata_from_title(title: str) -> dict:
    result = {"institution": None, "industry": [], "publish_date": None}
    for inst in KNOWN_INSTITUTIONS:
        if inst in title:
            result["institution"] = inst
            break
    if not result["institution"]:
        m = _BRACKET_INST.search(title)
        if m:
            sn = m.group(1)
            for inst in KNOWN_INSTITUTIONS:
                if sn in inst or inst in sn:
                    result["institution"] = inst
                    break
    if not result["institution"]:
        for short, full in INST_SHORT_MAP.items():
            if short in title[:30]:
                result["institution"] = full
                break
    for kw, industry in INDUSTRY_KEYWORDS.items():
        if kw in title and industry not in result["industry"]:
            result["industry"].append(industry)
    for pattern, fmt in [(_RE_DATE_YMD, "YYMMDD"), (_RE_DATE_FULL, "YYYYMMDD"), (_RE_DATE_CN, "CN")]:
        m = pattern.search(title)
        if m:
            if fmt == "YYMMDD":
                y = int("20" + m.group(1))
            else:
                y = int(m.group(1))
            try:
                result["publish_date"] = date(y, int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
            break
    return result


def _extract_meta_from_text(text: str) -> dict:
    snippet = text[:1000]
    result = {"institution": None, "publish_date": None, "analyst": [], "industry": []}

    for alias, full in INST_ALIAS_MAP.items():
        if alias in snippet:
            result["institution"] = full
            break
    if not result["institution"]:
        for inst in KNOWN_INSTITUTIONS:
            if inst in snippet:
                result["institution"] = inst
                break
    if not result["institution"]:
        m = re.search(r"([一-鿿]{2,6}证券(?:研究所|股份有限公司)?)", snippet)
        if m:
            result["institution"] = m.group(1).replace("研究所", "").replace("股份有限公司", "")

    if m := _RE_DATE_CN.search(snippet):
        try:
            result["publish_date"] = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    for m in _RE_ANALYST1.finditer(snippet):
        result["analyst"].append(m.group(1))
    for m in _RE_ANALYST2.finditer(snippet):
        name = m.group(1)
        if name not in result["analyst"]:
            result["analyst"].append(name)
    # 国金格式：扩大搜索范围到前5000字
    if not result["analyst"]:
        for m in _RE_ANALYST2.finditer(text[:5000]):
            name = m.group(1)
            if name not in result["analyst"]:
                result["analyst"].append(name)

    for kw, industry in INDUSTRY_KEYWORDS.items():
        if kw in snippet and industry not in result["industry"]:
            result["industry"].append(industry)
    return result


def _extract_symbols(text: str) -> list[str]:
    symbols = []
    seen = set()
    for pattern in [_RE_SYMBOL_DOT, _RE_SYMBOL_SH]:
        for m in pattern.finditer(text):
            code = m.group(0).upper()
            if code not in seen:
                seen.add(code)
                symbols.append(code)
    for m in _RE_SYMBOL_BRACKET.finditer(text):
        code = m.group(1)
        if code not in seen:
            seen.add(code)
            symbols.append(code)
    return symbols[:30]


def _extract_industries_from_text(text: str) -> list[str]:
    snippet = text[:5000]
    return list(dict.fromkeys(
        ind for kw, ind in INDUSTRY_KEYWORDS.items()
        if kw in snippet
    ))


# ========================================================================
# 图片提取
# ========================================================================

def _infer_figure_type(w: int, h: int, size_kb: int) -> str:
    ratio = w / max(h, 1)
    if w < 100 or h < 100 or ratio > 6:
        return "decorative"
    if ratio > 1.3 or size_kb > 30:
        return "chart"
    if 0.8 < ratio < 1.3 and size_kb < 20:
        return "decorative"
    return "image"


def _collect_page_captions(doc: fitz.Document, page_count: int) -> dict[int, list[str]]:
    captions = {}
    for pi in range(1, page_count + 1):
        try:
            caps = _RE_FIGURE_CAPTION.findall(doc[pi - 1].get_text())
            if caps:
                captions[pi] = [c[:256] for c in caps]
        except Exception:
            logger.debug("caption 提取失败 page=%d", pi)
    return captions


def _extract_images(doc: fitz.Document) -> list[dict]:
    """
    单次页面遍历，提取所有图片（光栅 + 矢量块渲染 + 整页渲染）。
    返回 list[dict]，每个 dict 包含 raw_bytes / width / height / page_number / caption 等。
    达到 FIGURE_MAX_PER_REPORT 上限后停止。
    """
    page_count = len(doc)
    page_captions = _collect_page_captions(doc, page_count)
    seen_md5: set[str] = set()
    seen_xrefs: set[int] = set()
    figures: list[dict] = []

    def _add_figure(page_idx: int, img_bytes: bytes, w: int, h: int) -> bool:
        if len(figures) >= FIGURE_MAX_PER_REPORT:
            return False
        md5 = hashlib.md5(img_bytes).hexdigest()
        if md5 in seen_md5:
            return True
        seen_md5.add(md5)

        sz = len(img_bytes) // 1024
        # TODO(v3): bbox就近匹配提升图注准确率。当前按插入顺序匹配，
        # 三类图片（光栅/矢量块/整页）混合插入，同页多图可能错位。
        caps = page_captions.get(page_idx, [])
        fig_idx_in_page = sum(1 for f in figures if f["page_number"] == page_idx)
        caption = caps[fig_idx_in_page] if fig_idx_in_page < len(caps) else None
        if caption and len(caps) > 1 and fig_idx_in_page < len(caps):
            logger.debug("图注匹配 page=%d idx=%d/%d caption=%s",
                        page_idx, fig_idx_in_page, len(caps), caption[:40])

        figures.append({
            "page_number": page_idx,
            "figure_order": len(figures) + 1,
            "figure_type": _infer_figure_type(w, h, sz),
            "caption": caption[:512] if caption else None,
            "image_size_kb": sz,
            "bytes": img_bytes,
            "width": w,
            "height": h,
        })
        return True

    for page_idx, page in enumerate(doc, start=1):
        page_w, page_h = page.rect.width, page.rect.height
        text = page.get_text()
        blocks = page.get_text("dict")["blocks"]
        img_blocks = [b for b in blocks if b["type"] == 1]
        drawings = page.get_drawings()

        # -- 光栅图 --
        for img in page.get_images(full=True):
            if len(figures) >= FIGURE_MAX_PER_REPORT:
                break
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            pix = None
            try:
                pix = fitz.Pixmap(doc, xref)
                try:
                    if pix.n >= 5:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    w, h = pix.width, pix.height
                    img_bytes = pix.tobytes("png")
                    if len(img_bytes) >= FIGURE_MIN_BYTES:
                        _add_figure(page_idx, img_bytes, w, h)
                finally:
                    pix.destroy()
                    pix = None
            except Exception:
                logger.warning("光栅图提取失败 page=%d xref=%d\n%s", page_idx, xref, traceback.format_exc())
                if pix:
                    try:
                        pix.destroy()
                    except Exception:
                        pass
                    pix = None

        if len(figures) >= FIGURE_MAX_PER_REPORT:
            break

        # -- 矢量块渲染 --
        for blk in img_blocks:
            if len(figures) >= FIGURE_MAX_PER_REPORT:
                break
            w, h = blk.get("width", 0), blk.get("height", 0)
            if w < 150 or h < 150 or w / max(h, 1) > 6:
                continue
            if w > page_w * 0.95 or h > page_h * 0.95:
                continue
            try:
                margin = min(_MERGE_MARGIN, (page_w - w) / 2, (page_h - h) / 2)
                bbox = blk["bbox"]
                clip = fitz.Rect(
                    max(0, bbox[0] - margin), max(0, bbox[1] - margin),
                    min(page_w, bbox[2] + margin), min(page_h, bbox[3] + margin * 2),
                )
                pix = page.get_pixmap(clip=clip, dpi=_DPI_RENDER)
                try:
                    img_bytes = pix.tobytes("png")
                    if len(img_bytes) >= _VECTOR_MIN_BYTES:
                        _add_figure(page_idx, img_bytes, int(clip.width), int(clip.height))
                finally:
                    pix.destroy()
                    pix = None
            except Exception:
                logger.debug("矢量块渲染失败 page=%d\n%s", page_idx, traceback.format_exc())

        if len(figures) >= FIGURE_MAX_PER_REPORT:
            break

        # -- 整页渲染（纯矢量图表） --
        large_img_blocks = [b for b in img_blocks if b.get("width", 0) > 150 and b.get("height", 0) > 150]
        if len(drawings) < _DRAWING_THRESHOLD or large_img_blocks:
            continue
        if not _RE_CHART_CAPTION.search(text):
            continue
        if len(figures) >= FIGURE_MAX_PER_REPORT:
            break

        try:
            pix = page.get_pixmap(dpi=_DPI_RENDER)
            try:
                img_bytes = pix.tobytes("png")
                if len(img_bytes) >= _PAGE_RENDER_MIN_BYTES:
                    _add_figure(page_idx, img_bytes,
                                int(page_w * _DPI_RENDER / 72),
                                int(page_h * _DPI_RENDER / 72))
            finally:
                pix.destroy()
                pix = None
        except Exception:
            logger.debug("整页渲染失败 page=%d\n%s", page_idx, traceback.format_exc())

    return figures


# ========================================================================
# 主解析函数
# ========================================================================

@dataclass
class ParseResult:
    title: str
    page_count: int
    full_text: str
    display_text: str
    file_hash: str
    file_size_kb: int
    institution: Optional[str] = None
    analyst: Optional[list[str]] = field(default_factory=list)
    publish_date: Optional[date] = None
    industry: Optional[list[str]] = field(default_factory=list)
    symbols: Optional[list[str]] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "page_count": self.page_count,
            "full_text": self.full_text,
            "display_text": self.display_text,
            "file_hash": self.file_hash,
            "file_size_kb": self.file_size_kb,
            "institution": self.institution,
            "analyst": self.analyst,
            "publish_date": self.publish_date,
            "industry": self.industry,
            "symbols": self.symbols,
            "figures": self.figures,
        }


def parse_pdf(pdf_path: Path) -> ParseResult:
    """
    解析单个研报 PDF，返回 ParseResult。
    纯解析函数，不写入磁盘文件。
    """
    doc = None
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        meta = doc.metadata or {}

        # -- 标题 --
        raw_title = (meta.get("title") or "").strip()
        if not raw_title or raw_title == "Untitled":
            raw_title = pdf_path.stem
        title = _extract_title(raw_title, pdf_path.name)

        # -- 全文 --
        pages_text = [page.get_text() for page in doc if page.get_text().strip()]
        full_text = normalize_text("\n".join(pages_text))

        if _RE_HASH.match(title):
            t = _extract_title_from_text(full_text)
            if t:
                title = t

        # -- 元数据 --
        meta_info = _parse_metadata_from_title(title)
        text_meta = _extract_meta_from_text(full_text)
        if not meta_info["institution"]:
            meta_info["institution"] = text_meta["institution"]
        if not meta_info["publish_date"]:
            meta_info["publish_date"] = text_meta["publish_date"]
        analyst_list = text_meta["analyst"]
        if meta_info["industry"]:
            for ind in text_meta.get("industry", []):
                if ind not in meta_info["industry"]:
                    meta_info["industry"].append(ind)
        else:
            meta_info["industry"] = text_meta.get("industry", [])
            if not meta_info["industry"]:
                meta_info["industry"] = _extract_industries_from_text(full_text)

        symbols = _extract_symbols(full_text)

        # -- 文件 --
        file_hash = compute_file_hash(pdf_path)
        file_size_kb = pdf_path.stat().st_size // 1024

        # -- 图片 --
        figures = _extract_images(doc)

        return ParseResult(
            title=title,
            page_count=page_count,
            full_text=full_text,
            display_text=clean_display_text(full_text),
            file_hash=file_hash,
            file_size_kb=file_size_kb,
            institution=meta_info["institution"],
            analyst=analyst_list[:5] if analyst_list else [],
            publish_date=meta_info["publish_date"],
            industry=meta_info["industry"],
            symbols=symbols,
            figures=figures,
        )
    except fitz.FileDataError as e:
        logger.error("加密/损坏PDF: %s — %s", pdf_path, e)
        raise
    except Exception:
        logger.exception("PDF解析异常: %s", pdf_path)
        raise
    finally:
        if doc:
            try:
                doc.close()
            except Exception:
                pass
