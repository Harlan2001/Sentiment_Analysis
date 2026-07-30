"""
研报PDF规范化命名工具
- 递归扫描源目录，计算 SHA256 哈希
- 按文件修改时间归集到 data/pdf/research/original/{年}/{月}/
- 输出 JSON 报告
"""
import hashlib
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.config.config import BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_hash")

DATA_ROOT = BASE_DIR / "data"
_PDF_MAGIC = b"%PDF-"


def compute_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def _validate_pdf(file_path: Path) -> bool:
    """校验文件合法性：大小>0 且 PDF 文件头"""
    try:
        if file_path.stat().st_size == 0:
            logger.warning("跳过空文件: %s", file_path)
            return False
        with open(file_path, "rb") as f:
            header = f.read(4)
        if header != _PDF_MAGIC:
            logger.warning("跳过非PDF: %s", file_path)
            return False
    except OSError as e:
        logger.error("文件读取失败 %s: %s", file_path, e)
        return False
    return True


def _get_archive_month(file_path: Path) -> str:
    """优先文件修改时间，其次创建时间，兜底当前月"""
    mtime = file_path.stat().st_mtime
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%Y/%m")


def normalize_pdf(src_path: Path, dest_dir: Path, dry_run: bool = False) -> dict | None:
    if not _validate_pdf(src_path):
        return None

    file_hash = compute_hash(src_path)
    dest_path = dest_dir / f"{file_hash}.pdf"

    result = {
        "src": str(src_path),
        "hash": file_hash,
        "dest": str(dest_path),
        "size_kb": src_path.stat().st_size // 1024,
    }

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            existing_hash = compute_hash(dest_path)
            if existing_hash == file_hash:
                logger.debug("跳过(已存在): %s", dest_path.name)
                return result
            logger.warning("hash冲突，覆盖: %s", dest_path.name)
        shutil.copy(src_path, dest_path)
        logger.info("%s -> %s", src_path.name, dest_path.name)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/research_hash.py <PDF目录> [--dry-run] [--month=YYYY/MM]")
        print("示例: python scripts/research_hash.py data/research/")
        print("      python scripts/research_hash.py data/research/ --month=2026/07")
        sys.exit(1)

    src_dir = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    # 按月归档：优先--month参数，其次文件修改时间，兜底当前月
    month_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--month=")), None)

    if not src_dir.is_dir():
        logger.error("目录不存在: %s", src_dir)
        sys.exit(1)

    logger.info("源目录: %s 模式: %s", src_dir, "DRY RUN" if dry_run else "正式执行")

    pdf_files = sorted(src_dir.rglob("*.pdf"))
    logger.info("找到 %d 份 PDF", len(pdf_files))

    results = []
    for pdf in pdf_files:
        try:
            # 按文件修改时间归档
            archive_month = month_arg or _get_archive_month(pdf)
            dest_dir = DATA_ROOT / "pdf" / "research" / "original" / archive_month

            result = normalize_pdf(pdf, dest_dir, dry_run)
            if result:
                results.append(result)
        except Exception as e:
            logger.error("处理失败 %s: %s", pdf.name, e)

    logger.info("完成: %d/%d 份", len(results), len(pdf_files))

    # 输出报告
    report_path = Path("data/research_hash_report.json")
    if not dry_run:
        report_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("报告: %s", report_path)

    for r in results:
        print(f"  {Path(r['src']).name} -> {Path(r['dest']).name}")
