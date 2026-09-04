"""
重建「集成测试专用库」并应用全部 schema。

安全护栏（用户明示"数据库操作一定要注意"，本脚本第一职责是防止误伤生产库）：
1. 目标库名硬校验：必须以 `_test` 结尾，且仅允许 [A-Za-z0-9_]，否则直接拒绝执行。
2. 库名来源：优先 MYSQL_TEST_DATABASE 环境变量（CI 显式给）；未设置时默认 Sentiment_analysis_test。
3. 绝不触碰生产库 Sentiment_analysis：即使误传也会因不满足 `_test` 结尾被拒绝。
4. --if-needed：目标库已含核心表 news 则跳过整个重建（加速本地迭代）。

Schema 来源（仓库现状是没有完整建库脚本，按以下顺序合成）：
- docs/表结构.md   19 个核心业务表 DDL（生产表结构文档，解析 CREATE TABLE 语句后补充分号执行）
- sql/*.sql        按文件名升序执行的增量迁移（workbench / ai_strategy / macro 等）
- 代码内联 DDL     llm_usage_log / dashboard_metric_cache 等在应用启动 ensure_tables() 时自动建，
                   本脚本不重复建（P3 用例依赖应用启动或显式建表时机）

用法：
    uv run python scripts/migrate_test_db.py              # 重建测试库
    uv run python scripts/migrate_test_db.py --if-needed  # 已有核心表则跳过
"""  # noqa: E501

import os
import re
import sys
from pathlib import Path

import pymysql

# Windows 控制台默认 GBK, 强制 stdout/stderr 均 UTF-8 保证中文日志/错误可读（CI 为 UTF-8, 不受影响）
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / "sql"
SCHEMA_DOC = BASE_DIR / "docs" / "表结构.md"

# 尝试加载根目录 .env（本地开发机有 .env；CI 由 workflow 显式传 env，此处不会覆盖已设值）
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    load_dotenv = None

# ---------------------------------------------------------------------------
# 连接参数（与 backend.config 同源环境变量；此处不 import backend，避免任何副作用）
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


HOST = _env("MYSQL_HOST", "127.0.0.1")
PORT = int(_env("MYSQL_PORT", "3306"))
USER = _env("MYSQL_USER", "root")
PASSWORD = _env("MYSQL_PASSWORD")
TEST_DB = _env("MYSQL_TEST_DATABASE", "Sentiment_analysis_test")


def _validate_test_db_name(db_name: str) -> None:
    """硬校验：只允许在 *_test 库上执行破坏性操作。"""
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        sys.exit(f"[拒绝] 库名含非法字符: {db_name!r}")
    if not db_name.endswith("_test"):
        sys.exit(
            f"[拒绝] 目标库名必须以 _test 结尾, 当前为 {db_name!r}。"
            f"这是防止误触生产库 {os.getenv('MYSQL_DATABASE', 'Sentiment_analysis')!r} 的保护。"
        )


def _connect():
    conn = pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        charset="utf8mb4",
        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
    )
    return conn


def _db_exists(conn, db_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
            (db_name,),
        )
        return cur.fetchone() is not None


def _core_table_exists(conn, db_name: str, table: str = "news") -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (db_name, table),
        )
        return cur.fetchone() is not None


def _apply_script(conn, label: str, sql_text: str) -> None:
    """执行一段 SQL（可含多语句）。失败时抛出带 label 的异常。"""
    try:
        with conn.cursor() as cur:
            cur.execute(sql_text)
    except Exception as exc:
        raise RuntimeError(f"执行 {label} 失败: {exc}") from exc


def _sql_files_sorted() -> list:
    files = sorted(SQL_DIR.glob("*.sql"), key=lambda p: p.name)
    if not files:
        raise RuntimeError(f"sql/ 目录为空: {SQL_DIR}")
    return files


def _extract_core_ddl_from_doc(doc: Path) -> list:
    """从 docs/表结构.md 提取 CREATE TABLE 语句, 补分号并注入 IF NOT EXISTS。"""
    text = doc.read_text(encoding="utf-8")
    blocks = re.findall(r"CREATE TABLE.*?(?=\n---\s*\n|\Z)", text, re.DOTALL)
    statements = []
    for block in blocks:
        stmt = block.strip()
        if not stmt or not stmt.upper().startswith("CREATE TABLE"):
            continue
        # 统一成可重复执行（该文档 DDL 没有任何分号结尾）
        if stmt.startswith("CREATE TABLE"):
            stmt = stmt.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
        if not stmt.rstrip().endswith(";"):
            stmt = stmt.rstrip() + ";"
        statements.append(stmt)
    return statements


def _apply_core_schema(conn, db_name: str) -> int:
    """应用核心业务表 DDL（docs/表结构.md）, 返回成功表数。"""
    statements = _extract_core_ddl_from_doc(SCHEMA_DOC)
    if not statements:
        raise RuntimeError(f"未能从 {SCHEMA_DOC} 提取任何 CREATE TABLE")
    conn.select_db(db_name)
    applied = 0
    for idx, stmt in enumerate(statements, start=1):
        table_name = re.search(r"CREATE TABLE IF NOT EXISTS [`]?([A-Za-z0-9_]+)", stmt)
        label = f"{SCHEMA_DOC} 第{idx}个 DDL" + (
            f" ({table_name.group(1)})" if table_name else ""
        )
        _apply_script(conn, label, stmt)
        applied += 1
    return applied


# sql/ 中不得在「新建测试库」时应用的脚本：
# - *_down.sql            回滚脚本（语义是撤销迁移, 不是建库）
# - migration_company_dept.sql / migration_token_usage.sql
#                         历史数据补丁: 给 users 加列用 ALTER ... AFTER <既有列>（依赖生产已有列）,
#                         且 UPDATE 真实行; 新建的空测试库运行必然失败, 且语义不适合 schema 构建。
#   （llm_usage_log 等表由代码 ensure_tables() 自动建, 见 backend/common/llm_logger.py）
MIGRATIONS_SKIP = {
    "migration_company_dept.sql",
    "migration_token_usage.sql",
}


def _apply_incremental_migrations(conn, db_name: str) -> int:
    """按文件名升序应用 sql/*.sql, 返回成功文件数（跳过回滚/数据补丁脚本）。"""
    conn.select_db(db_name)
    files = _sql_files_sorted()
    applied = 0
    for file in files:
        if file.name.endswith("_down.sql") or file.name in MIGRATIONS_SKIP:
            print(f"[migrate] 跳过(非建库脚本): {file.name}")
            continue
        sql_text = file.read_text(encoding="utf-8")
        _apply_script(conn, str(file.relative_to(BASE_DIR)), sql_text)
        applied += 1
    return applied


def main() -> None:
    _validate_test_db_name(TEST_DB)
    print(f"[migrate] 目标测试库: {TEST_DB}  (host={HOST}:{PORT})")

    conn = _connect()
    try:
        if _core_table_exists(conn, TEST_DB, "news"):
            print(f"[migrate] {TEST_DB} 已含核心表 news")
            if "--if-needed" in sys.argv:
                print("[migrate] --if-needed: 跳过重建, 退出。")
                return
            print("[migrate] 未带 --if-needed, 继续重建。")

        # 重建: DROP -> CREATE -> USE
        conn.query(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
        conn.query(f"CREATE DATABASE `{TEST_DB}` "
                   "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        print(f"[migrate] 已重建数据库 {TEST_DB}")

        n_core = _apply_core_schema(conn, TEST_DB)
        print(f"[migrate] 核心业务表 DDL 应用 {n_core} 个 (来源 docs/表结构.md)")

        n_inc = _apply_incremental_migrations(conn, TEST_DB)
        print(f"[migrate] 增量迁移应用 {n_inc} 个文件 (来源 sql/*.sql)")

        # 汇总统计
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s",
                (TEST_DB,),
            )
            total = cur.fetchone()[0]
        print(f"[migrate] 完成: {TEST_DB} 共 {total} 张表")
    finally:
        conn.close()


if __name__ == "__main__":
    main()