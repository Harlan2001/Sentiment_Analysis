"""管理员功能测试 — 只测 JWT 权限标识和路由权限校验，不操作真实数据库。"""


from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX

# 与 admin_app 中间件校验共用，保证签发的 token 能被本地中间件验证
TEST_ADMIN_SECRET = "test-admin-secret-key-0123456789abcdef"


# ── 测试 fixture ──

@pytest.fixture
def admin_app():
    """构建一个带认证中间件的迷你 FastAPI 应用，用于测试权限路由。

    直接 patch 模块级 AUTH_ENABLED / JWT_SECRET_KEY，而非 setenv + importlib.reload：
    config.py 在加载时以 override=True 重读 .env（load_dotenv），
    测试期内设置的 AUTH_ENABLED 会被 .env 覆盖，靠 reload 翻转 AUTH_ENABLED 不可靠。
    """
    from backend.auth.dependencies import auth_middleware

    app = FastAPI()
    app.middleware("http")(auth_middleware)

    @app.get(f"{API_PREFIX}/workbench/users")
    def list_users(request: Request):
        if not getattr(request.state, "is_admin", False):
            return JSONResponse(status_code=403, content={"detail": "需要管理员权限"})
        return {"data": [{"id": 1, "username": "admin"}]}

    @app.get(f"{API_PREFIX}/market")
    def market_data(request: Request):
        return {"data": "public"}

    with patch("backend.auth.dependencies.AUTH_ENABLED", True), \
         patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
        yield app


@pytest.fixture
def admin_token() -> str:
    """生成 admin JWT token。"""
    from backend.auth.auth import create_jwt_token

    with patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
        return create_jwt_token("admin", is_admin=True, role="admin")


@pytest.fixture
def member_token() -> str:
    """生成普通成员 JWT token（role 走规范角色 "member"→"user" 归一化）。"""
    from backend.auth.auth import create_jwt_token

    with patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
        return create_jwt_token("user1", is_admin=False, role="member")


# ── JWT 权限标识 ──

class TestAdminJwtClaims:
    def test_admin_jwt_contains_is_admin_true(self):
        """JWT payload 正确包含 is_admin=true。

        直接 patch 模块级 JWT_SECRET_KEY，而非 setenv + importlib.reload：
        config.py 已被缓存，重载 auth 模块不会重读环境变量，CI 下 JWT_SECRET_KEY 为空会抛 InvalidKeyError。
        """
        from backend.auth.auth import create_jwt_token, verify_jwt_token

        with patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
            token = create_jwt_token("admin", is_admin=True, role="admin")
            payload = verify_jwt_token(token)

        assert payload["sub"] == "admin"
        assert payload["is_admin"] is True
        assert payload["role"] == "admin"

    def test_member_jwt_is_admin_false(self):
        """普通成员 JWT 的 is_admin=false。"""
        from backend.auth.auth import create_jwt_token, verify_jwt_token

        with patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
            token = create_jwt_token("user1", is_admin=False, role="member")
            payload = verify_jwt_token(token)

        assert payload["sub"] == "user1"
        assert payload["is_admin"] is False
        assert payload["role"] == "member"

    def test_admin_role_vs_member_role_in_token(self):
        """admin 和 member 角色的 token 包含不同的 role 值。"""
        from backend.auth.auth import create_jwt_token, verify_jwt_token

        with patch("backend.auth.auth.JWT_SECRET_KEY", TEST_ADMIN_SECRET):
            admin_token_val = create_jwt_token("admin", is_admin=True, role="admin")
            member_token_val = create_jwt_token("user1", is_admin=False, role="member")

            admin_payload = verify_jwt_token(admin_token_val)
            member_payload = verify_jwt_token(member_token_val)

        assert admin_payload["role"] == "admin"
        assert member_payload["role"] == "member"


# ── 管理员路由权限 ──

class TestAdminRouteAccess:
    def test_admin_can_access_admin_route(self, admin_app, admin_token):
        """admin 用户 GET /workbench/users → 200。"""
        client = TestClient(admin_app)
        r = client.get(
            f"{API_PREFIX}/workbench/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    def test_member_cannot_access_admin_route(self, admin_app, member_token):
        """普通成员 GET /workbench/users → 403。"""
        client = TestClient(admin_app)
        r = client.get(
            f"{API_PREFIX}/workbench/users",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert r.status_code == 403

    def test_anonymous_cannot_access_admin_route(self, admin_app):
        """匿名用户 GET /workbench/users → 403（anonymous 是 visitor 非 admin）。"""
        client = TestClient(admin_app)
        r = client.get(f"{API_PREFIX}/workbench/users")
        assert r.status_code == 403

    def test_admin_can_access_public_route(self, admin_app, admin_token):
        """admin 用户可以访问公开路由 /market。"""
        client = TestClient(admin_app)
        r = client.get(
            f"{API_PREFIX}/market",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    def test_member_can_access_public_route(self, admin_app, member_token):
        """普通成员可以访问公开路由 /market。"""
        client = TestClient(admin_app)
        r = client.get(
            f"{API_PREFIX}/market",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert r.status_code == 200