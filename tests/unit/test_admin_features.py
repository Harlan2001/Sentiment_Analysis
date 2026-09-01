"""管理员功能测试 — 只测 JWT 权限标识和路由权限校验，不操作真实数据库。"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.auth.auth import create_jwt_token, verify_jwt_token
from backend.auth.dependencies import auth_middleware
from backend.config.config import API_PREFIX


# ── 测试 fixture ──

@pytest.fixture
def admin_app(monkeypatch) -> FastAPI:
    """构建一个带认证中间件的迷你 FastAPI 应用，用于测试权限路由。"""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-admin-secret-key")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8080/v1")
    # 重新加载模块以获取新的环境变量
    import importlib
    import backend.config.config as cfg
    import backend.auth.auth as auth_mod
    import backend.auth.dependencies as deps
    importlib.reload(cfg)
    importlib.reload(auth_mod)
    importlib.reload(deps)

    app = FastAPI()
    app.middleware("http")(deps.auth_middleware)

    @app.get(f"{API_PREFIX}/workbench/users")
    def list_users(request: Request):
        if not getattr(request.state, "is_admin", False):
            return JSONResponse(status_code=403, content={"detail": "需要管理员权限"})
        return {"data": [{"id": 1, "username": "admin"}]}

    @app.get(f"{API_PREFIX}/market")
    def market_data(request: Request):
        return {"data": "public"}

    return app


@pytest.fixture
def admin_token(monkeypatch) -> str:
    """生成 admin JWT token。"""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-admin-secret-key")
    import importlib
    import backend.auth.auth as auth_mod
    importlib.reload(auth_mod)
    return auth_mod.create_jwt_token("admin", is_admin=True, role="admin")


@pytest.fixture
def member_token(monkeypatch) -> str:
    """生成普通成员 JWT token。"""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-admin-secret-key")
    import importlib
    import backend.auth.auth as auth_mod
    importlib.reload(auth_mod)
    return auth_mod.create_jwt_token("user1", is_admin=False, role="member")


# ── JWT 权限标识 ──

class TestAdminJwtClaims:
    def test_admin_jwt_contains_is_admin_true(self, monkeypatch):
        """JWT payload 正确包含 is_admin=true。"""
        monkeypatch.setenv("JWT_SECRET_KEY", "test-admin-jwt-secret")
        import importlib
        import backend.auth.auth as auth_mod
        importlib.reload(auth_mod)

        token = auth_mod.create_jwt_token("admin", is_admin=True, role="admin")
        payload = auth_mod.verify_jwt_token(token)

        assert payload["sub"] == "admin"
        assert payload["is_admin"] is True
        assert payload["role"] == "admin"

    def test_member_jwt_is_admin_false(self, monkeypatch):
        """普通成员 JWT 的 is_admin=false。"""
        monkeypatch.setenv("JWT_SECRET_KEY", "test-member-jwt-secret")
        import importlib
        import backend.auth.auth as auth_mod
        importlib.reload(auth_mod)

        token = auth_mod.create_jwt_token("user1", is_admin=False, role="member")
        payload = auth_mod.verify_jwt_token(token)

        assert payload["sub"] == "user1"
        assert payload["is_admin"] is False
        assert payload["role"] == "member"

    def test_admin_role_vs_member_role_in_token(self, monkeypatch):
        """admin 和 member 角色的 token 包含不同的 role 值。"""
        monkeypatch.setenv("JWT_SECRET_KEY", "test-role-jwt-secret")
        import importlib
        import backend.auth.auth as auth_mod
        importlib.reload(auth_mod)

        admin_token_val = auth_mod.create_jwt_token("admin", is_admin=True, role="admin")
        member_token_val = auth_mod.create_jwt_token("user1", is_admin=False, role="member")

        admin_payload = auth_mod.verify_jwt_token(admin_token_val)
        member_payload = auth_mod.verify_jwt_token(member_token_val)

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