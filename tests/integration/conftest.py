"""
tests/integration 的 conftest。

集成测试铁律：**必须显式设置 MYSQL_TEST_DATABASE**（且以 `_test` 结尾）才允许运行。
未设置一律 skip —— 这是防止测试误连生产库 Sentiment_analysis 的第一道闸。

P3 起在 session 级初始化测试库连接池（database.py 的 PooledDB），
让 db_operations / repositories 层使用真实测试库；并提供清表工具。
schema 由 CI workflow 或本地脚本 scripts/migrate_test_db.py 提前重建。
"""

import os

import pymysql
import pytest

# 在 backend.config（其 import 时会 load_dotenv(override=True) 用 .env 覆盖 MYSQL_HOST 等）
# 被 import 之前，缓存命令行/CI 传入的 MySQL 连接地址 —— 避免本地 .env 把集成测试引向生产主机。
# 集成测试一律连「显式指定的 MySQL」+ 「*_test 测试库」，不碰生产库。
_APP_MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1").strip()
_APP_MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
_APP_MYSQL_USER = os.getenv("MYSQL_USER", "root").strip()
_APP_MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
_APP_MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4").strip() or "utf8mb4"


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
    """指向测试库的原始 pymysql 连接（不经 database.py 的池, 供造数与断言）。"""
    try:
        conn = pymysql.connect(
            host=_APP_MYSQL_HOST, port=_APP_MYSQL_PORT,
            user=_APP_MYSQL_USER, password=_APP_MYSQL_PASSWORD,
            database=test_db_name, charset=_APP_MYSQL_CHARSET,
            autocommit=True,  # 造数即时生效, 供连接池另一条会话(execute_query/pool)读到
        )
    except pymysql.MySQLError as exc:
        pytest.fail(
            f"无法连接测试库 {test_db_name}@{_APP_MYSQL_HOST}:{_APP_MYSQL_PORT}: {exc}。"
            f"请先运行: uv run python scripts/migrate_test_db.py"
        )
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _init_db_pool(test_db_name):
    """session 级初始化测试库连接池, 让 database 层/get_db_connection 可用。

    连接参数用「显式指定的 MySQL + *_test 测试库」（上方缓存的 env, 不读 config.MYSQL_CONFIG,
    避免本地 .env 把 host 覆盖为生产主机）。绝不碰生产库 Sentiment_analysis。
    """
    from backend.common.database import DatabaseConfig, init_database

    init_database(
        DatabaseConfig(
            host=_APP_MYSQL_HOST,
            port=_APP_MYSQL_PORT,
            user=_APP_MYSQL_USER,
            password=_APP_MYSQL_PASSWORD,
            database=test_db_name,
            charset=_APP_MYSQL_CHARSET,
        ),
        max_connections=5,
    )
    yield


@pytest.fixture
def clean_tables(mysql_conn):
    """对指定表 TRUNCATE（关闭外键检查后执行, 兼容表间 FK）。"""

    def _clean(*tables):
        mysql_conn.query("SET FOREIGN_KEY_CHECKS=0")
        for table in tables:
            mysql_conn.query(f"TRUNCATE TABLE `{table}`")
        mysql_conn.query("SET FOREIGN_KEY_CHECKS=1")

    return _clean


def pytest_collection_modifyitems(config, items):
    """tests/integration 下的所有用例统一标记 integration（免 + 各文件重复打标）。"""
    for item in items:
        if "integration" not in item.keywords:
            item.add_marker(pytest.mark.integration)