"""测试公共夹具：在模块加载时 mock 数据库，避免 init_database() 连接真实数据库。"""

import os
from unittest.mock import MagicMock, patch

# 测试模块会在 fixture 执行前导入应用配置，因此必须先提供测试默认值。
os.environ.setdefault("LLM_API_KEY", "test-llm-api-key")
os.environ.setdefault("LLM_BASE_URL", "https://test-llm.example.com/v1")
os.environ.setdefault("USE_LOCAL_SNAPSHOT", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-bytes")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")
os.environ.setdefault("MYSQL_DATABASE", "test_db")

# ── 模块级别 mock：pytest 加载 conftest 时立即生效，早于任何 test 文件导入 ──
_mock_conn = MagicMock()
_mock_cursor = MagicMock()
_mock_cursor.fetchone.return_value = None
_mock_cursor.fetchall.return_value = []
_mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=_mock_cursor)
_mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
_mock_conn.get_connection_params.return_value = {
    "host": "localhost", "user": "test", "password": "test",
    "database": "test_db", "charset": "utf8mb4", "autocommit": True,
    "port": 3306, "cursorclass": MagicMock(),
}

_patch = patch("pymysql.connect", return_value=_mock_conn)
_patch.start()

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-llm-api-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://test-llm.example.com/v1")
    monkeypatch.setenv("MYSQL_HOST", "localhost")
    monkeypatch.setenv("MYSQL_USER", "test")
    monkeypatch.setenv("MYSQL_PASSWORD", "test")
    monkeypatch.setenv("MYSQL_DATABASE", "test_db")
