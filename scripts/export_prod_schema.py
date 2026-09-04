"""从生产库导出全库表结构到 sql/schema_full.sql（**只读**, 供 migrate_test_db.py 重建测试库用）。

用法:
    uv run python scripts/export_prod_schema.py \
        --db Sentiment_analysis --confirm-prod --output sql/schema_full.sql

安全护栏（用户明示"数据库操作一定要注意"）:
    - **仅只读**: 只执行 SHOW CREATE TABLE 与 information_schema 查询, 不改生产库任何数据/结构。
    - 必须显式传 --confirm-prod: 确认你清楚这是在连「生产库」做只读导出。
    - 目标库名禁止 *_test 结尾: 防止误把测试库当生产库导出。
    - 产出的 sql/schema_full.sql 提交进仓库, 作为测试库 schema 的权威来源;
      CI 在离线环境据此重建 Sentiment_analysis_test。
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

import pymysql

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = BASE_DIR / "sql" / "schema_full.sql"

# 允许 --db 覆盖生产库名（如 Sentiment_analysis）, 禁止以 _test 结尾
_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _fail(msg: str) -> None:
    print(f"[拒绝] {msg}", file=sys.stderr)
    sys.exit(1)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _quote_ident(ident: str) -> str:
    """对库名/表名加反引号（配合 _IDENT_RE 校验防注入）。"""
    if not _IDENT_RE.match(ident):
        _fail(f"标识符含非法字符: {ident!r}")
    return f"`{ident}`"


def main() -> None:
    parser = argparse.ArgumentParser(description="只读导出生产库表结构到 sql/schema_full.sql")
    parser.add_argument(
        "--db",
        default=_env("MYSQL_DATABASE", "") or "Sentiment_analysis",
        help="生产库名（默认 MYSQL_DATABASE 或 Sentiment_analysis）",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--confirm-prod",
        action="store_true",
        help="确认你明知这是连生产库做只读导出",
    )
    parser.add_argument("--host", default=_env("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(_env("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=_env("MYSQL_USER", "root"))
    parser.add_argument("--password", default=_env("MYSQL_PASSWORD", ""))
    args = parser.parse_args()

    if not args.confirm_prod:
        _fail("必须显式加 --confirm-prod（你是要连生产库做只读导出, 请确认）")
    if not args.db:
        _fail("数据库名不能为空")
    if args.db.endswith("_test"):
        _fail(
            f"目标库名 {args.db!r} 以 _test 结尾, 疑似测试库。"
            "本脚本只应从生产库导出, 拒绝操作。"
        )
    if not _IDENT_RE.match(args.db):
        _fail(f"数据库名含非法字符: {args.db!r}")

    print(f"[export] 目标(生产)库: {args.db} @ {args.host}:{args.port}  [仅只读]")

    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                (args.db,),
            )
            tables = [row[0] for row in cur.fetchall()]
        if not tables:
            _fail(f"库 {args.db} 中没有找到任何基础表, 检查库名与连接权限")

        create_statements = []
        with conn.cursor() as cur:
            for tbl in tables:
                cur.execute(f"SHOW CREATE TABLE {_quote_ident(args.db)}.{_quote_ident(tbl)}")
                create_statements.append(cur.fetchone()[1])
    finally:
        conn.close()

    lines = [
        f"-- 生产库 {args.db} 表结构只读快照（由 scripts/export_prod_schema.py 生成）",
        f"-- 生成时间: {datetime.datetime.now():%Y-%m-%d %H:%M}; 用于重建测试库 Sentiment_analysis_test",
        "SET FOREIGN_KEY_CHECKS=0;",
    ]
    for tbl in tables:
        lines.append(f"DROP TABLE IF EXISTS {_quote_ident(tbl)};")
    for create_sql in create_statements:
        lines.append(create_sql.rstrip().rstrip(";") + ";")
    lines.append("SET FOREIGN_KEY_CHECKS=1;")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(f"[export] 完成: 导出 {len(tables)} 张表 -> {output}")
    print("[export] 提醒: 这是只读操作, 未修改生产库任何数据/结构。")
    print("[export] 请把该文件提交进仓库, migrate_test_db.py 会用它重建测试库。")


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass
    main()