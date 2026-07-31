"""
研报入库脚本
- 扫描 data/pdf/research/original/ 下的所有 PDF
- 调用 parser.parse_pdf 解析
- 图片写入磁盘，元数据写入 MySQL（research_report + report_figure）
"""
import json
import logging
import os
import shutil
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config.config import BASE_DIR
from backend.research_report.parser import parse_pdf, compute_file_hash, ParseResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_research")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "10.253.50.134"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "Sentiment_analysis_test"),
    "charset": "utf8mb4",
}

DATA_ROOT = BASE_DIR / "data"
PDF_ROOT = Path(os.getenv("RESEARCH_PDF_ROOT", str(DATA_ROOT / "pdf" / "research" / "original")))
FIGURE_ROOT = Path(os.getenv("RESEARCH_FIGURE_ROOT", str(DATA_ROOT / "pdf" / "research")))


def get_connection():
    """获取非自动提交的数据库连接"""
    return pymysql.connect(**DB_CONFIG, autocommit=False)


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _infer_report_type(industry: list[str], title: str) -> str:
    t = " ".join(industry) + title
    if any(kw in t for kw in ["固收", "债券", "国债", "债市", "宏观", "GDP"]):
        return "macro"
    if any(kw in t for kw in ["策略", "周报", "晨会", "日报"]):
        return "strategy"
    if any(kw in t for kw in ["公司", "深度"]):
        return "company"
    return "industry"


def _infer_source(rel_path: str) -> str:
    return "seed" if "seed" in rel_path else "eastmoney"


def _clear_existing(cursor):
    cursor.execute("DELETE FROM report_figure")
    cursor.execute("DELETE FROM research_report")
    cursor.execute("ALTER TABLE research_report AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE report_figure AUTO_INCREMENT = 1")


def _clean_figure_dir(hash_dir: Path):
    if hash_dir.exists():
        shutil.rmtree(hash_dir)
    hash_dir.mkdir(parents=True, exist_ok=True)


def _write_figures(figures: list[dict], file_hash: str) -> list[dict]:
    """将图片 bytes 写入磁盘，返回带路径的 figure 列表"""
    hash_dir = FIGURE_ROOT / "figure" / file_hash
    _clean_figure_dir(hash_dir)
    result = []
    for fig in figures:
        img_bytes = fig.pop("bytes")
        w = fig.pop("width")
        h = fig.pop("height")
        fig_path = hash_dir / f'p{fig["page_number"]}_f{fig["figure_order"]}.png'
        fig_path.write_bytes(img_bytes)
        fig["image_path"] = str(fig_path.relative_to(FIGURE_ROOT))
        fig["image_size_kb"] = len(img_bytes) // 1024
        result.append(fig)
    return result


def ingest_one(pdf_path: Path, conn) -> int | None:
    """单份入库，事务包裹：全部成功 commit，异常 rollback"""
    filename = pdf_path.name
    logger.info("解析: %s", filename[:60])

    try:
        result: ParseResult = parse_pdf(pdf_path)
    except Exception as e:
        logger.error("解析失败 %s: %s", pdf_path.name, e)
        return None

    if len(result.full_text) < 50:
        logger.warning("全文过短(%d字): %s", len(result.full_text), filename)

    report_type = _infer_report_type(result.industry, result.title)

    try:
        rel_path = str(pdf_path.relative_to(DATA_ROOT))
    except ValueError:
        rel_path = str(pdf_path)

    source = _infer_source(rel_path)

    # 图片写入磁盘（原子：先写临时目录再重命名）
    figures = _write_figures(result.figures, result.file_hash)

    with conn.cursor() as cur:
        # 入库前二次校验 hash
        cur.execute("SELECT id FROM research_report WHERE file_hash=%s", (result.file_hash,))
        if cur.fetchone():
            logger.debug("跳过(已存在): hash=%s", result.file_hash)
            return None

        cur.execute("""
            INSERT INTO research_report
            (title, institution, analyst, publish_date, industry, symbols, report_type,
             file_path, file_hash, file_size_kb, page_count,
             full_text, status, source, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'parsed', %s, 'admin')
        """, (
            result.title[:512],
            result.institution,
            ", ".join(result.analyst) if result.analyst else None,
            result.publish_date,
            ", ".join(result.industry) if result.industry else None,
            ", ".join(result.symbols) if result.symbols else None,
            report_type,
            rel_path[:512],
            result.file_hash,
            result.file_size_kb,
            result.page_count,
            result.full_text,
            source,
        ))
        report_id = cur.lastrowid

        for fig in figures:
            cur.execute("""
                INSERT INTO report_figure
                (report_id, page_number, figure_order, figure_type, caption,
                 image_path, image_size_kb)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                report_id, fig["page_number"], fig["figure_order"],
                fig.get("figure_type"), fig.get("caption"),
                fig["image_path"][:512], fig["image_size_kb"],
            ))

    conn.commit()
    inst = result.institution or "-"
    ind = ", ".join(result.industry[:2]) if result.industry else "-"
    logger.info("完成 id=%d | %s | %s | %d图 | %d页", report_id, inst, ind, len(figures), result.page_count)
    return report_id


def main():
    import argparse
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument("--full", action="store_true", help="清空全部数据重新入库")
    args = parser_args.parse_args()

    if args.full:
        confirm = input("[WARN] 确认清空全部研报数据并重新入库? 输入 y/N: ")
        if confirm.strip().lower() != "y":
            print("已取消")
            return

    conn = get_connection()
    logger.info("数据库: %s:%s/%s", DB_CONFIG["host"], DB_CONFIG["port"], DB_CONFIG["database"])
    logger.info("扫描: %s", PDF_ROOT)
    logger.info("模式: %s", "全量重入" if args.full else "增量")

    stray = DATA_ROOT / "pdf" / "research" / "original" / "2026" / "figure"
    if stray.exists():
        shutil.rmtree(stray)

    if args.full:
        figure_dir = FIGURE_ROOT / "figure"
        if figure_dir.exists():
            shutil.rmtree(figure_dir)
        with conn.cursor() as cur:
            _clear_existing(cur)
        conn.commit()

    existing_hashes = set()
    if not args.full:
        with conn.cursor() as cur:
            cur.execute("SELECT file_hash FROM research_report")
            existing_hashes = {r[0] for r in cur.fetchall()}
    conn.close()

    pdf_files = sorted(PDF_ROOT.rglob("*.pdf"))
    logger.info("找到 %d 份 PDF", len(pdf_files))

    success = skipped = failed = 0
    for pdf in pdf_files:
        try:
            if not args.full:
                h = compute_file_hash(pdf)
                if h in existing_hashes:
                    skipped += 1
                    continue

            rid = ingest_one(pdf, get_connection())
            if rid:
                success += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error("失败 %s: %s", pdf.name, e)

    logger.info("入库完成: 新增=%d 跳过=%d 失败=%d", success, skipped, failed)

    conn2 = get_connection()
    with conn2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM research_report")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM report_figure")
        total_figs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM research_report WHERE institution IS NOT NULL")
        has_inst = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM research_report WHERE industry IS NOT NULL AND industry != ''")
        has_ind = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM research_report WHERE symbols IS NOT NULL AND symbols != ''")
        has_sym = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM research_report WHERE publish_date IS NOT NULL")
        has_date = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM research_report WHERE analyst IS NOT NULL AND analyst != ''")
        has_analyst = cur.fetchone()[0]
        cur.execute("SELECT status, COUNT(*) FROM research_report GROUP BY status")
        statuses = cur.fetchall()
    conn2.close()

    logger.info("汇总: report=%d fig=%d | 机构:%d 行业:%d 标的:%d 日期:%d 分析师:%d",
                total, total_figs, has_inst, has_ind, has_sym, has_date, has_analyst)
    logger.info("状态: %s", statuses)


if __name__ == "__main__":
    main()
