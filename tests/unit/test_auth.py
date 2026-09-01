"""认证模块单元测试：密码验证、JWT 签发/验证、认证中间件。

只测不碰数据库的纯函数和中间件逻辑。
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.auth.auth import check_password

# ---------------------------------------------------------------------------
# 密码验证
# ---------------------------------------------------------------------------

class TestCheckPassword:
    def test_correct_password_returns_true(self):
        assert check_password("admin123", "admin123") is True

    def test_wrong_password_returns_false(self):
        assert check_password("admin123", "wrong") is False

    def test_empty_password(self):
        assert check_password("", "") is True
        assert check_password("user", "") is False

    def test_none_password(self):
        """None 与 None 比对，None 与字符串比对。"""
        assert check_password(None, None) is True
        assert check_password("user", None) is False


# ---------------------------------------------------------------------------
# JWT 签发与验证
# ---------------------------------------------------------------------------

class TestJWT:
    """JWT 纯逻辑测试：签发、验证、过期。"""

    @pytest.fixture(autouse=True)
    def _patch_jwt_config(self):
        """注入测试用密钥，避免依赖真实 .env。"""
        with patch("backend.auth.auth.JWT_SECRET_KEY", "test-jwt-secret"), \
             patch("backend.auth.auth.JWT_EXPIRY_HOURS", 24):
            yield

    def test_create_token_contains_claims(self):
        from backend.auth.auth import create_jwt_token
        token = create_jwt_token("admin", is_admin=True, role="admin")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_token_returns_payload(self):
        from backend.auth.auth import create_jwt_token, verify_jwt_token
        token = create_jwt_token("user1", is_admin=False, role="member")
        payload = verify_jwt_token(token)
        assert payload["sub"] == "user1"
        assert payload["is_admin"] is False
        assert payload["role"] == "member"

    def test_verify_token_with_admin_role(self):
        from backend.auth.auth import create_jwt_token, verify_jwt_token
        token = create_jwt_token("admin", is_admin=True, role="admin")
        payload = verify_jwt_token(token)
        assert payload["sub"] == "admin"
        assert payload["is_admin"] is True
        assert payload["role"] == "admin"

    def test_verify_expired_token_raises(self):
        from backend.auth.auth import create_jwt_token, verify_jwt_token
        with patch("backend.auth.auth.JWT_EXPIRY_HOURS", -1):
            token = create_jwt_token("user1")
        with pytest.raises(Exception):
            verify_jwt_token(token)

    def test_verify_invalid_token_raises(self):
        from backend.auth.auth import verify_jwt_token
        with pytest.raises(Exception):
            verify_jwt_token("not-a-valid-jwt-token")

    def test_verify_tampered_token_raises(self):
        from backend.auth.auth import create_jwt_token, verify_jwt_token
        token = create_jwt_token("user1")
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(Exception):
            verify_jwt_token(tampered)

    def test_token_iat_is_recent(self):
        from backend.auth.auth import create_jwt_token, verify_jwt_token
        now = int(time.time())
        token = create_jwt_token("user1")
        payload = verify_jwt_token(token)
        assert abs(payload["iat"] - now) <= 5


# ---------------------------------------------------------------------------
# 认证中间件
# ---------------------------------------------------------------------------

def _mock_request(path: str, method: str = "GET", auth_header: str | None = None,
                  query_token: str | None = None) -> MagicMock:
    """构建一个最小化的 FastAPI Request mock。"""
    req = MagicMock(spec=Request)
    req.url.path = path
    req.method = method
    req.headers = MagicMock()
    req.headers.get.return_value = auth_header
    req.query_params = MagicMock()
    req.query_params.get.return_value = query_token
    req.state = MagicMock()
    return req


class TestAuthMiddleware:
    """认证中间件行为测试。"""

    @pytest.fixture(autouse=True)
    def _patch_middleware_deps(self):
        """注入测试环境变量与 token 验证函数。"""
        with patch("backend.auth.dependencies.AUTH_ENABLED", True), \
             patch("backend.auth.dependencies.API_PREFIX", "/sapi"), \
             patch("backend.auth.dependencies.INTERNAL_TOKEN", "internal-test-token"):
            yield

    # ---- 免登录模式 ----

    @pytest.mark.asyncio
    async def test_auth_disabled_passes_as_admin(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/workbench/conversations", method="POST")
        call_next = AsyncMock(return_value=MagicMock())

        with patch("backend.auth.dependencies.AUTH_ENABLED", False):
            await auth_middleware(req, call_next)

        assert req.state.username == "admin"
        assert req.state.is_admin is True
        assert req.state.role == "admin"
        call_next.assert_awaited_once()

    # ---- 公开路径 ----

    @pytest.mark.asyncio
    async def test_public_path_login_skips_auth(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/auth/login", method="POST")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_public_path_health_skips_auth(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/health", method="GET")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_public_path_docs_skips_auth(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/docs", method="GET")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_public_path_openapi_skips_auth(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/openapi.json", method="GET")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        call_next.assert_awaited_once()

    # ---- OPTIONS 预检 ----

    @pytest.mark.asyncio
    async def test_options_preflight_skips_auth(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/workbench/conversations", method="OPTIONS")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        call_next.assert_awaited_once()

    # ---- 无 token 场景 ----

    @pytest.mark.asyncio
    async def test_no_token_safe_method_becomes_anonymous(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/news", method="GET")
        call_next = AsyncMock(return_value=MagicMock())
        await auth_middleware(req, call_next)
        assert req.state.username == "anonymous"
        assert req.state.is_admin is False
        assert req.state.role == "visitor"

    @pytest.mark.asyncio
    async def test_no_token_unsafe_method_returns_401(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/workbench/conversations", method="POST")
        call_next = AsyncMock()
        resp = await auth_middleware(req, call_next)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 401
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_token_delete_returns_401(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/workbench/conversations/abc", method="DELETE")
        call_next = AsyncMock()
        resp = await auth_middleware(req, call_next)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 401

    # ---- 有效 token ----

    @pytest.mark.asyncio
    async def test_valid_token_sets_identity(self):
        from backend.auth.dependencies import auth_middleware
        valid_payload = {"sub": "user1", "is_admin": False, "role": "member"}
        req = _mock_request("/sapi/workbench/conversations", method="POST",
                            auth_header="Bearer valid-token")
        call_next = AsyncMock(return_value=MagicMock())

        with patch("backend.auth.dependencies.verify_jwt_token", return_value=valid_payload):
            await auth_middleware(req, call_next)

        assert req.state.username == "user1"
        assert req.state.is_admin is False
        assert req.state.role == "member"
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_token_admin_role(self):
        from backend.auth.dependencies import auth_middleware
        admin_payload = {"sub": "admin", "is_admin": True, "role": "admin"}
        req = _mock_request("/sapi/workbench/users", method="GET",
                            auth_header="Bearer admin-token")
        call_next = AsyncMock(return_value=MagicMock())

        with patch("backend.auth.dependencies.verify_jwt_token", return_value=admin_payload):
            await auth_middleware(req, call_next)

        assert req.state.username == "admin"
        assert req.state.is_admin is True
        assert req.state.role == "admin"

    # ---- 过期/无效 token ----

    @pytest.mark.asyncio
    async def test_expired_token_safe_method_becomes_anonymous(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/news", method="GET", auth_header="Bearer expired-token")
        call_next = AsyncMock(return_value=MagicMock())

        with patch("backend.auth.dependencies.verify_jwt_token", side_effect=Exception("expired")):
            await auth_middleware(req, call_next)

        assert req.state.username == "anonymous"
        assert req.state.role == "visitor"

    @pytest.mark.asyncio
    async def test_expired_token_unsafe_method_returns_401(self):
        from backend.auth.dependencies import auth_middleware
        req = _mock_request("/sapi/workbench/conversations", method="POST",
                            auth_header="Bearer expired-token")
        call_next = AsyncMock()

        with patch("backend.auth.dependencies.verify_jwt_token", side_effect=Exception("expired")):
            resp = await auth_middleware(req, call_next)

        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 401

    # ---- 内部服务 token ----

    @pytest.mark.asyncio
    async def test_internal_token_passes_as_admin(self):
        from backend.auth.dependencies import auth_middleware
        # 使用非公开路径，否则 PUBLIC_PATHS 会跳过认证
        req = _mock_request("/sapi/workbench/conversations", method="POST",
                            auth_header="Bearer internal-test-token")
        call_next = AsyncMock(return_value=MagicMock())

        await auth_middleware(req, call_next)

        assert req.state.username == "internal-service"
        assert req.state.is_admin is True
        assert req.state.role == "admin"

    # ---- SSE query param token ----

    @pytest.mark.asyncio
    async def test_sse_token_from_query_param(self):
        from backend.auth.dependencies import auth_middleware
        valid_payload = {"sub": "user1", "is_admin": False, "role": "member"}
        req = _mock_request("/sapi/workbench/conversations/abc/messages", method="POST",
                            query_token="sse-token")
        call_next = AsyncMock(return_value=MagicMock())

        with patch("backend.auth.dependencies.verify_jwt_token", return_value=valid_payload):
            await auth_middleware(req, call_next)

        assert req.state.username == "user1"