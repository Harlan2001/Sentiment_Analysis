"""
PDF 转高清图片工具。

功能：
1. 扫描 data/pdf/ 目录，获取最新 PDF 报告
2. 将 PDF 逐页转换为高清 PNG 图片（默认 200 DPI，适合公众号图文）
3. 支持命令行调用，可指定 PDF 路径和分辨率

使用方式：
    python backend/pdf_png.py                          # 自动找最新 PDF 转换
    python backend/pdf_png.py --pdf-path data/pdf/2026-04-24.pdf
    python backend/pdf_png.py --dpi 300                # 超高清模式
"""

try:
    import pymupdf
    _HAS_PYMUPDF = True
except ImportError:
    pymupdf = None  # type: ignore
    _HAS_PYMUPDF = False
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "pdf"
DEFAULT_OUTPUT_DIR = BASE_DIR / "temp_images"

logger = logging.getLogger("pdf_png")


def get_latest_pdf(pdf_dir: str | Path = None) -> Path | None:
    """
    获取 data/pdf/ 目录下最新的 PDF 文件（按修改时间排序）。

    :param pdf_dir: PDF 存放目录，默认 data/pdf/
    :return: 最新 PDF 的 Path，无文件时返回 None
    """
    target_dir = Path(pdf_dir) if pdf_dir else PDF_DIR

    if not target_dir.exists():
        logger.error("PDF 目录不存在: %s", target_dir)
        return None

    pdf_files = sorted(
        target_dir.glob("*.pdf"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not pdf_files:
        logger.warning("PDF 目录中没有找到 PDF 文件: %s", target_dir)
        return None

    latest = pdf_files[0]
    mtime = datetime.fromtimestamp(latest.stat().st_mtime)
    logger.info("找到最新 PDF: %s (修改时间: %s)", latest.name, mtime.strftime("%Y-%m-%d %H:%M:%S"))
    return latest


def pdf_to_images(pdf_path: str | Path, output_dir: str | Path = None, dpi: int = 200):
    """
    将 PDF 逐页转换为高清图片。

    :param pdf_path: PDF 文件路径
    :param output_dir: 临时图片保存目录，默认 temp_images/
    :param dpi: 图片分辨率（200 适合公众号图文，150 够用，300 超高清体积大）
    :return: 图片路径列表
    """
    if not _HAS_PYMUPDF:
        raise ImportError(
            "pymupdf 未安装，无法转换 PDF 为图片。请安装: pip install pymupdf"
        )
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 清空临时目录中的旧图片
    for file in output_dir.iterdir():
        if file.suffix.lower() in (".png", ".jpg", ".jpeg"):
            file.unlink()
            logger.debug("已删除旧图片: %s", file.name)

    doc = pymupdf.open(str(pdf_path))
    image_paths = []

    logger.info("开始转换 PDF → 图片 (DPI=%d): %s", dpi, pdf_path.name)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # 使用 zoom 矩阵方式渲染，兼容性更好
        zoom = dpi / 72  # 72 是 PDF 标准 DPI
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        image_path = output_dir / f"page_{page_num + 1:02d}.png"
        pix.save(str(image_path))
        image_paths.append(str(image_path))
        logger.info(
            "  第 %d/%d 页 → %s (%dx%d)",
            page_num + 1, len(doc), image_path.name, pix.width, pix.height,
        )

    doc.close()
    logger.info("PDF 转换完成，共生成 %d 张图片，输出目录: %s", len(image_paths), output_dir)
    return image_paths


def main():
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="PDF 转高清图片工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python backend/pdf_png.py                           # 自动找最新 PDF
  python backend/pdf_png.py --pdf-path data/pdf/2026-04-24.pdf
  python backend/pdf_png.py --dpi 300 --output-dir high_res_images
        """,
    )
    parser.add_argument(
        "--pdf-path",
        default=None,
        help="PDF 文件路径（默认自动查找 data/pdf/ 下最新文件）",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="输出图片 DPI（默认 200，适合公众号；300 超高清）",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="图片输出目录（默认 temp_images/）",
    )
    args = parser.parse_args()

    # 确定 PDF 路径
    pdf_path = args.pdf_path
    if not pdf_path:
        latest = get_latest_pdf()
        if not latest:
            logger.error("未找到任何 PDF 文件，请先运行 pdf_generator.py 生成报告")
            sys.exit(1)
        pdf_path = str(latest)

    # 转换
    try:
        image_paths = pdf_to_images(
            pdf_path=pdf_path,
            output_dir=args.output_dir,
            dpi=args.dpi,
        )
        logger.info("转换成功: %d 张图片 → %s", len(image_paths), args.output_dir)
        for p in image_paths:
            logger.debug("  %s", p)
    except Exception as e:
        logger.exception("PDF 转图片失败")
        sys.exit(1)


if __name__ == "__main__":
    from backend.common.logging_config import setup_logging
    setup_logging()
    main()
