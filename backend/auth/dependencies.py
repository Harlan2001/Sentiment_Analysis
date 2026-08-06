"""
FastAPI 认证依赖 + HTTP 中间件
"""

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.auth.auth import verify_jwt_token
from backend.config.config import API_PREFIX, AUTH_ENABLED

# 不需要认证的路径
PUBLIC_PATHS = {
    f"{API_PREFIX}/auth/login",
    f"{API_PREFIX}/auth/login/phone",
    f"{API_PREFIX}/auth/status",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    f"{API_PREFIX}/internal/pipeline/trigger",
}

# 内部服务调用 token — agent tool executor 通过 SENTIMENT_INTERNAL_API_TOKEN
# 环境变量配置，发起内部 HTTP 调用时携带此 token，中间件识别后以 admin 放行。
INTERNAL_TOKEN = os.environ.get("SENTIMENT_INTERNAL_API_TOKEN")


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
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        # SSE / EventSource 不支持自定义 header，从 query param 获取
        token = request.query_params.get("token")

    # 内部服务 token — agent 内部 HTTP 调用免认证
    if INTERNAL_TOKEN and token == INTERNAL_TOKEN:
        request.state.username = "internal-service"
        request.state.is_admin = True
        request.state.role = "admin"
        return await call_next(request)

    if not token:
        return JSONResponse(status_code=401, content={"detail": "未登录，请先登录"})

    try:
        payload = verify_jwt_token(token)
        request.state.username = payload["sub"]
        request.state.is_admin = payload.get("is_admin", False)
        request.state.role = payload.get("role", "user")
    except Exception:
        return JSONResponse(
            status_code=401, content={"detail": "登录已过期，请重新登录"}
        )

    return await call_next(request)
