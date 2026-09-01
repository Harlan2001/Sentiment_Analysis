"""
FastAPI 认证依赖 + HTTP 中间件
"""

import os

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.auth.auth import normalize_role, verify_jwt_token
from backend.config.config import API_PREFIX, AUTH_ENABLED

# 公开路径：仅放行登录/健康检查/文档。写操作一律不在此放行；
# 内部流水线触发端接口改走 INTERNAL_TOKEN 鉴权（见下方中间件逻辑），勿放回此集合。
PUBLIC_PATHS = {
    f"{API_PREFIX}/auth/login",
    f"{API_PREFIX}/auth/login/phone",
    f"{API_PREFIX}/auth/status",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    f"{API_PREFIX}/mcp/feishu/callback",
}

# 内部服务调用 token — agent tool executor 通过 SENTIMENT_INTERNAL_API_TOKEN
# 环境变量配置，发起内部 HTTP 调用时携带此 token，中间件识别后以 admin 放行。
INTERNAL_TOKEN = os.environ.get("SENTIMENT_INTERNAL_API_TOKEN")

# 只读方法：匿名访客仅放行这些方法（数据可浏览），写操作/管理接口仍需登录
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def extract_bearer_token(request: Request) -> str | None:
    """从 Authorization header 提取 Bearer token；
    SSE/EventSource 不支持自定义 header，兜底从 query param ?token= 获取。"""
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
    return request.query_params.get("token")


async def auth_middleware(request: Request, call_next):
    """
    全局认证中间件：
    - AUTH_ENABLED=false 时直接放行
    - AUTH_ENABLED=true 时验证 Bearer token
    - 公开路径（login/health等）始终放行
    - 内部服务 token 识别为 admin 放行
    """
    if not AUTH_ENABLED:
        # 免登录模式：所有使用归入 admin 账户，方便 Token 统计
        request.state.username = "admin"
        request.state.is_admin = True
        request.state.role = "admin"
        return await call_next(request)

    # 公开路径跳过认证
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # OPTIONS 预检请求放行
    if request.method == "OPTIONS":
        return await call_next(request)

    # 验证 Authorization header 或 query param token（SSE 连接用）
    token = extract_bearer_token(request)

    # 内部服务 token — agent 内部 HTTP 调用免认证
    if INTERNAL_TOKEN and token == INTERNAL_TOKEN:
        request.state.username = "internal-service"
        request.state.is_admin = True
        request.state.role = "admin"
        return await call_next(request)

    # 匿名只读访客身份（仅放行 GET/HEAD/OPTIONS）
    def _as_anonymous_reader():
        request.state.username = "anonymous"
        request.state.is_admin = False
        request.state.role = "visitor"
        return call_next(request)

    if not token:
        if request.method in SAFE_METHODS:
            return await _as_anonymous_reader()
        return JSONResponse(status_code=401, content={"detail": "未登录，请先登录"})

    try:
        payload = verify_jwt_token(token)
    except jwt.InvalidTokenError:
        # token 无效（过期等）：只读请求按访客放行，写操作仍要求重新登录
        if request.method in SAFE_METHODS:
            return await _as_anonymous_reader()
        return JSONResponse(
            status_code=401, content={"detail": "登录已过期，请重新登录"}
        )

    username = payload.get("sub")
    if not username:
        # 缺少 sub 声明的 token 视为无效
        if request.method in SAFE_METHODS:
            return await _as_anonymous_reader()
        return JSONResponse(
            status_code=401, content={"detail": "登录已过期，请重新登录"}
        )

    request.state.username = username
    request.state.is_admin = bool(payload.get("is_admin", False))
    request.state.role = normalize_role(payload.get("role"))
    return await call_next(request)
