"""
研报 AI 分析批量脚本
- 分批读取 status='parsed' 的研报
- 先抢占任务锁（UPDATE status='processing'），再执行
- 支持重试、冷却、超时、图片校验
- 统一用 doubao 模型（支持多模态识图）
"""
import json as json_mod
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pymysql
from backend.config.config import BASE_DIR
from backend.research_report.llm import analyze_report, MODEL_OPTIONS
from backend.research_report.constants import FIGURE_MAX_PER_REPORT
from backend.common.llm_logger import log_llm_usage
from backend.common.database import DatabaseConfig, init_database
from backend.config.config import MYSQL_CONFIG

# 初始化连接池（供 llm_logger 使用）
init_database(DatabaseConfig(**MYSQL_CONFIG))

# ---- 日志 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("analyze_research")

# ---- 配置 ----
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "10.253.50.134"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "Sentiment_analysis_test"),
    "charset": "utf8mb4",
}

DATA_ROOT = BASE_DIR / "data"

MODEL_NAME = os.getenv("RESEARCH_ANALYSIS_MODEL", "doubao")
MODEL_FULL = MODEL_OPTIONS.get(MODEL_NAME, MODEL_OPTIONS["doubao"])

BATCH_SIZE = int(os.getenv("RESEARCH_BATCH_SIZE", "5"))
RATE_LIMIT_SEC = float(os.getenv("RESEARCH_RATE_LIMIT_SEC", "0.8"))
MAX_RETRIES = int(os.getenv("RESEARCH_MAX_RETRIES", "3"))
RETRY_COOLDOWN_SEC = float(os.getenv("RESEARCH_RETRY_COOLDOWN_SEC", "10"))
CALL_TIMEOUT_SEC = int(os.getenv("RESEARCH_CALL_TIMEOUT_SEC", "120"))


def _get_connection():
    return pymysql.connect(**DB_CONFIG, autocommit=False)


def _json(obj) -> str:
    return json_mod.dumps(obj, ensure_ascii=False)


def _get_figure_paths(cursor, report_id: int) -> list[Path]:
    cursor.execute(
        """SELECT image_path FROM report_figure
           WHERE report_id=%s AND image_size_kb > 15
           ORDER BY image_size_kb DESC LIMIT %s""",
        (report_id, FIGURE_MAX_PER_REPORT),
    )
    paths = []
    for (p,) in cursor.fetchall():
        fp = DATA_ROOT / p
        if fp.exists():
            paths.append(fp)
        else:
            logger.warning("图片缺失 rid=%d path=%s", report_id, p)
    return paths


def _claim_task(cursor, rid: int) -> bool:
    """抢占任务：只有 status IN ('parsed','failed') 且 retry_count < MAX_RETRIES 才能转为 processing"""
    cursor.execute("""
        UPDATE research_report SET status='processing'
        WHERE id=%s AND status IN ('parsed','failed')
          AND (retry_count IS NULL OR retry_count < %s)
    """, (rid, MAX_RETRIES))
    return cursor.rowcount > 0


def _mark_done(cursor, rid: int, parsed: dict, raw: str, usage: dict, elapsed: float):
    cursor.execute("""
        UPDATE research_report SET
            ai_summary=%s, ai_key_points=%s, ai_symbols=%s, ai_industries=%s,
            ai_market_view=%s, ai_view_strength=%s, ai_time_horizon=%s,
            ai_evidence=%s, ai_analyzed_at=NOW(), ai_model=%s, ai_raw_response=%s,
            status='analyzed', parse_error=NULL
        WHERE id=%s
    """, (
        str(parsed.get("summary", ""))[:1024],
        _json(parsed.get("key_points", [])),
        _json(parsed.get("symbols", [])),
        _json(parsed.get("industries", [])),
        parsed.get("market_view", "neutral"),
        float(parsed.get("view_strength", 0.5)),
        parsed.get("time_horizon", "medium"),
        _json(parsed.get("evidence", [])),
        MODEL_NAME,
        _json(raw) if isinstance(raw, str) else raw,
        rid,
    ))
    logger.info("完成 rid=%d view=%s symbols=%d tokens=%d elapsed=%.1fs",
                rid, parsed.get("market_view", "?"),
                len(parsed.get("symbols", [])), usage["total_tokens"], elapsed)


def _mark_failed(cursor, rid: int, error_msg: str):
    cursor.execute("""
        UPDATE research_report SET
            status='failed', parse_error=%s,
            retry_count=COALESCE(retry_count,0)+1
        WHERE id=%s
    """, (error_msg[:500], rid))


def _process_one(rid: int, title: str, full_text: str):
    """处理单份研报（已抢占锁），返回 (success, error_message)"""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            figure_paths = _get_figure_paths(cur, rid)

        t0 = time.time()
        parsed, raw, usage = analyze_report(
            full_text,
            figure_paths=figure_paths if figure_paths else None,
            model=MODEL_FULL,
        )
        elapsed = time.time() - t0

        if "error" in parsed:
            logger.warning("LLM解析警告 rid=%d: %s", rid, parsed["error"][:100])

        with conn.cursor() as cur:
            _mark_done(cur, rid, parsed, raw, usage, elapsed)
        conn.commit()

        log_llm_usage(
            call_source="research",
            model_name=MODEL_NAME,
            provider_model=MODEL_FULL,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            success=True,
        )
        return True, None
    except Exception as e:
        err = str(e)[:500]
        logger.error("失败 rid=%d: %s\n%s", rid, err, traceback.format_exc())
        try:
            with conn.cursor() as cur:
                _mark_failed(cur, rid, err)
            conn.commit()
        except Exception:
            pass
        log_llm_usage(
            call_source="research",
            model_name=MODEL_NAME,
            provider_model=MODEL_FULL,
            success=False,
            error_message=err,
        )
        return False, err
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    logger.info("启动 batch=%d rate_limit=%.1fs retries=%d model=%s",
                BATCH_SIZE, RATE_LIMIT_SEC, MAX_RETRIES, MODEL_FULL)

    conn = _get_connection()
    try:
        # 先重置卡住的 processing 任务（超时恢复）
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE research_report SET status='failed'
                WHERE status='processing'
                  AND updated_at < NOW() - INTERVAL 30 MINUTE
            """)
            if cur.rowcount:
                logger.info("恢复超时任务: %d条", cur.rowcount)

            # 获取待处理总数
            cur.execute("""
                SELECT COUNT(*) FROM research_report
                WHERE status IN ('parsed','failed')
                  AND (retry_count IS NULL OR retry_count < %s)
            """, (MAX_RETRIES,))
            total_pending = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    if total_pending == 0:
        logger.info("没有待分析的研报")
        return

    logger.info("待分析: %d 份", total_pending)
    success = failed = 0

    while True:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                # 分批读取
                cur.execute("""
                    SELECT id, title, full_text FROM research_report
                    WHERE status IN ('parsed','failed')
                      AND (retry_count IS NULL OR retry_count < %s)
                    ORDER BY retry_count ASC, id ASC
                    LIMIT %s
                """, (MAX_RETRIES, BATCH_SIZE))
                batch = cur.fetchall()
            conn.commit()
        finally:
            conn.close()

        if not batch:
            break

        for rid, title, full_text in batch:
            # 抢占
            conn = _get_connection()
            try:
                with conn.cursor() as cur:
                    if not _claim_task(cur, rid):
                        logger.debug("抢占失败 rid=%d（已被其他进程处理）", rid)
                        continue
                conn.commit()
            finally:
                conn.close()

            logger.info("处理 rid=%d [%s]", rid, title[:50])
            ok, err = _process_one(rid, title, full_text)
            if ok:
                success += 1
            else:
                failed += 1
            time.sleep(RATE_LIMIT_SEC)

    logger.info("完成: 成功=%d 失败=%d", success, failed)

    # 汇总
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) FROM research_report GROUP BY status")
            for s, c in cur.fetchall():
                logger.info("  %s: %d", s, c)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
