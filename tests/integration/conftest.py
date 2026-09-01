"""
tests/integration 的 conftest。

集成测试铁律：**必须显式设置 MYSQL_TEST_DATABASE**（且以 `_test` 结尾）才允许运行。
未设置一律 skip —— 这是防止测试误连生产库 Sentiment_analysis 的第一道闸。

P1 阶段只提供连接检查与库存在性冒烟；不 init_database、不自动 migrate
（CI 由 workflow 显式跑 scripts/migrate_test_db.py）。P3 再补 session 级
migrate + clean_tables(TRUNCATE) 等 fixture。
"""

import os

import pymysql
import pytest


def _test_db_name() -> str:
    name = os.getenv("MYSQL_TEST_DATABASE", "").strip()
    if not name:
        pytest.skip(
            "未设置 MYSQL_TEST_DATABASE, 跳过集成测试"
            "（避免误连生产库 Sentiment_analysis; 本地可设 MYSQL_TEST_DATABASE=Sentiment_analysis_test）"
        )
    if not name.endswith("_test"):
        pytest.fail(
            f"MYSQL_TEST_DATABASE 必须以 _test 结尾, 当前为 {name!r}。"
            "绝不可以在非测试库上运行集成测试。"
        )
    return name


@pytest.fixture(scope="session")
def test_db_name() -> str:
    """经硬校验的测试库名; 未设置 MYSQL_TEST_DATABASE 时 session 直接 skip。"""
    return _test_db_name()


@pytest.fixture(scope="session")
def mysql_conn(test_db_name: str):
    """指向测试库的原始 pymysql 连接（不经 database.py 的池, P1 冒烟专用）。"""
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    try:
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=test_db_name, charset="utf8mb4",
        )
    except pymysql.MySQLError as exc:
        pytest.fail(
            f"无法连接测试库 {test_db_name}@{host}:{port}: {exc}。"
            f"请先运行: uv run python scripts/migrate_test_db.py"
        )
    yield conn
    conn.close()