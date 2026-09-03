"""认证接口测试：登录、状态、用户信息。

使用 TestClient 测试 /sapi/auth/* 路由，数据库连接被 mock。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX

PREFIX = API_PREFIX
TEST_JWT_SECRET = "test-auth-routes-secret-at-least-32-bytes"


# ── 测试辅助 ──

def _make_cursor(fetchone_result=None, fetchall_result=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_result
    cursor.fetchall.return_value = fetchall_result or []
    cursor.rowcount = 0
    return cursor


def _mock_get_connection(cursor):
    """返回 mock 的 get_db_connection 函数（上下文管理器风格）。

    auth.py 现用 ``with get_db_connection() as conn:`` 取连接，故 mock 连接需
    支持 ``__enter__`` 返回自身，游标经 ``with conn.cursor() as cursor`` 暴露。
    """
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__.return_value = conn
    conn.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=conn)


# ── 登录 ──

class TestLogin:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        with patch("backend.routers.auth.AUTH_ENABLED", True), \
             patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
            yield

    def test_login_success(self):
        cursor = _make_cursor(fetchone_result=(1, "user1", "pass123", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "user1", "password": "pass123"})
            assert r.status_code == 200
            data = r.json()
            assert data["success"] is True
            assert data["token"] is not None
            assert data["username"] == "user1"

    def test_login_wrong_password(self):
        cursor = _make_cursor(fetchone_result=(1, "user1", "correct", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "user1", "password": "wrong"})
            assert r.status_code == 401

    def test_login_disabled_account(self):
        cursor = _make_cursor(fetchone_result=(1, "disabled", "pass", "已禁用", 0, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "disabled", "password": "pass"})
            assert r.status_code == 403

    def test_login_nonexistent_user(self):
        cursor = _make_cursor(fetchone_result=None)
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "nobody", "password": "x"})
            assert r.status_code == 401

    def test_login_returns_admin_role(self):
        cursor = _make_cursor(fetchone_result=(1, "admin", "admin123", "管理员", 1, 1, "admin"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "admin", "password": "admin123"})
            data = r.json()
            assert data["is_admin"] is True
            assert data["role"] == "admin"

    def test_login_returns_user_role(self):
        cursor = _make_cursor(fetchone_result=(1, "user1", "pass", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "user1", "password": "pass"})
            data = r.json()
            assert data["is_admin"] is False
            assert data["role"] == "user"

    def test_login_auth_disabled(self, monkeypatch):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.AUTH_ENABLED", False), \
             patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "admin", "password": "x"})
            assert r.status_code == 200
            data = r.json()
            assert data["success"] is True
            assert "免登录" in data["message"]


# ── 手机号登录 ──

class TestPhoneLogin:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        with patch("backend.routers.auth.AUTH_ENABLED", True), \
             patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
            yield

    def test_login_phone_success(self):
        cursor = _make_cursor(fetchone_result=(1, "user1", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login/phone", json={"phone": "13800138000"})
            assert r.status_code == 200
            data = r.json()
            assert data["success"] is True
            assert data["token"] is not None

    def test_login_phone_not_registered(self):
        cursor = _make_cursor(fetchone_result=None)
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login/phone", json={"phone": "13900000000"})
            assert r.status_code == 401

    def test_login_phone_disabled_account(self):
        cursor = _make_cursor(fetchone_result=(1, "disabled", "已禁用", 0, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login/phone", json={"phone": "13800138001"})
            assert r.status_code == 403

    def test_login_phone_auth_disabled(self, monkeypatch):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.AUTH_ENABLED", False), \
             patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login/phone", json={"phone": "13800138000"})
            assert r.status_code == 200
            assert "免登录" in r.json()["message"]


# ── 认证状态 ──

class TestAuthStatus:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        with patch("backend.routers.auth.AUTH_ENABLED", True), \
             patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
            yield

    def test_auth_status_no_auth(self, monkeypatch):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.AUTH_ENABLED", False), \
             patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(f"{PREFIX}/auth/status")
            data = r.json()
            assert data["auth_enabled"] is False
            assert data["authenticated"] is True
            assert data["is_admin"] is True

    def test_auth_status_authenticated(self):
        from backend.auth.auth import create_jwt_token
        token = create_jwt_token("user1", is_admin=False, role="member")

        cursor = _make_cursor(fetchone_result=(1, "user1", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(
                f"{PREFIX}/auth/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = r.json()
            assert data["authenticated"] is True
            assert data["username"] == "user1"

    def test_auth_status_unauthenticated(self):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(f"{PREFIX}/auth/status")
            data = r.json()
            assert data["auth_enabled"] is True
            assert data["authenticated"] is False

    def test_auth_status_invalid_token(self):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(
                f"{PREFIX}/auth/status",
                headers={"Authorization": "Bearer invalid.token.here"},
            )
            data = r.json()
            assert data["authenticated"] is False


# ── 用户信息 ──

class TestAuthMe:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        with patch("backend.routers.auth.AUTH_ENABLED", True), \
             patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
            yield

    def test_auth_me_authenticated(self):
        from backend.auth.auth import create_jwt_token
        token = create_jwt_token("user1", is_admin=False, role="member")

        cursor = _make_cursor(fetchone_result=(1, "user1", "用户一", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(
                f"{PREFIX}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()["data"]
            assert data["username"] == "user1"
            assert data["authenticated"] is True

    def test_auth_me_disabled_user(self):
        from backend.auth.auth import create_jwt_token
        token = create_jwt_token("disabled", is_admin=False, role="member")

        cursor = _make_cursor(fetchone_result=(1, "disabled", "已禁用", 0, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get(
                f"{PREFIX}/auth/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = r.json()
            assert data["authenticated"] is False


# ── 公开路径免认证 ──

class TestPublicPaths:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        with patch("backend.routers.auth.AUTH_ENABLED", True), \
             patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
            yield

    def test_login_endpoint_no_auth_required(self):
        cursor = _make_cursor(fetchone_result=(1, "user1", "pass", "用户", 1, 0, "user"))
        mock_conn = _mock_get_connection(cursor)

        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.post(f"{PREFIX}/auth/login", json={"username": "user1", "password": "pass"})
            assert r.status_code == 200

    def test_health_no_auth_required(self):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get("/health")
            assert r.status_code == 200

    def test_docs_no_auth_required(self):
        mock_conn = _mock_get_connection(_make_cursor())
        with patch("backend.routers.auth.get_db_connection", mock_conn):
            from backend.app import app
            client = TestClient(app)
            r = client.get("/docs")
            assert r.status_code == 200
