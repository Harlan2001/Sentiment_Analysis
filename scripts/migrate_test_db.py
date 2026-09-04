"""重建「集成测试专用库」并应用生产库权威 schema。

安全护栏（用户明示"数据库操作一定要注意"）:
1. 目标库名硬校验：必须以 `_test` 结尾，且仅允许 [A-Za-z0-9_]，否则直接拒绝执行。
2. 库名来源：MYSQL_TEST_DATABASE 环境变量；未设置时默认 Sentiment_analysis_test。
3. 绝不触碰生产库 Sentiment_analysis：即使误传也会因不满足 `_test` 结尾被拒绝。

Schema 来源:
    sql/schema_full.sql —— 生产库 DDL 的**只读导出快照**（scripts/export_prod_schema.py 生成,
    已提交仓库）。这是测试库结构的唯一权威来源, 保证与生产一致且 CI 可离线建库。
    生产 schema 演进后重新运行 export_prod_schema.py 更新该文件并提交。
    （原先基于 docs/表结构.md 与 sql/ 历史迁移的拼凑方案已废弃：文档过时、
      迁移脚本互相冲突且不可信。）

用法:
    uv run python scripts/migrate_test_db.py              # 重建测试库
    uv run python scripts/migrate_test_db.py --if-needed  # 已有核心表则跳过
"""

import os
import re
import sys
from pathlib import Path

import pymysql

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_SQL = BASE_DIR / "sql" / "schema_full.sql"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


HOST = _env("MYSQL_HOST", "127.0.0.1")
PORT = int(_env("MYSQL_PORT", "3306"))
USER = _env("MYSQL_USER", "root")
PASSWORD = _env("MYSQL_PASSWORD")
TEST_DB = _env("MYSQL_TEST_DATABASE", "Sentiment_analysis_test")

_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_test_db_name(db_name: str) -> None:
    """硬校验：只允许在 *_test 库上执行破坏性操作。"""
    if not _IDENT_RE.match(db_name):
        sys.exit(f"[拒绝] 库名含非法字符: {db_name!r}")
    if not db_name.endswith("_test"):
        sys.exit(
            f"[拒绝] 目标库名必须以 _test 结尾, 当前为 {db_name!r}。"
            f"这是防止误触生产库 {os.getenv('MYSQL_DATABASE', 'Sentiment_analysis')!r} 的保护。"
        )


def _connect():
    return pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        charset="utf8mb4",
        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
    )


def _core_table_exists(conn, db_name: str, table: str = "news") -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (db_name, table),
        )
        return cur.fetchone() is not None


def _apply_schema_file(conn, db_name: str) -> int:
    """应用 sql/schema_full.sql（含 SET FK=0 / DROP / CREATE 全套, 多语句）。"""
    if not SCHEMA_SQL.exists():
        sys.exit(
            f"[FAIL] 缺少 {SCHEMA_SQL}。请先在可信环境用只读脚本生成并提交: \n"
            "    uv run python scripts/export_prod_schema.py --db Sentiment_analysis "
            "--confirm-prod --output sql/schema_full.sql"
        )
    conn.select_db(db_name)
    sql_text = SCHEMA_SQL.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql_text)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s",
            (db_name,),
        )
        return cur.fetchone()[0]


def main() -> None:
    _validate_test_db_name(TEST_DB)
    print(f"[migrate] 目标测试库: {TEST_DB}  (host={HOST}:{PORT})")

    if not SCHEMA_SQL.exists():
        raise SystemExit(
            f"[FAIL] 缺少 {SCHEMA_SQL}。请先运行 scripts/export_prod_schema.py 生成并提交。"
        )

    conn = _connect()
    try:
        if _core_table_exists(conn, TEST_DB, "news"):
            print(f"[migrate] {TEST_DB} 已含核心表 news")
            if "--if-needed" in sys.argv:
                print("[migrate] --if-needed: 跳过重建, 退出。")
                return
            print("[migrate] 未带 --if-needed, 继续重建。")

        conn.query(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
        conn.query(
            f"CREATE DATABASE `{TEST_DB}` "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
        print(f"[migrate] 已重建数据库 {TEST_DB}")

        total = _apply_schema_file(conn, TEST_DB)
        print(f"[migrate] 完成: {TEST_DB} 共 {total} 张表 (来源 {SCHEMA_SQL.name})")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass
    main()