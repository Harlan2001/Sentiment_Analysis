"""
FastAPI 认证依赖 + HTTP 中间件
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.auth.auth import verify_jwt_token
from backend.config.config import AUTH_ENABLED

# 不需要认证的路径
PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/status",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


async def auth_middleware(request: Request, call_next):
    """
    全局认证中间件：
    - AUTH_ENABLED=false 时直接放行
    - AUTH_ENABLED=true 时验证 Bearer token
    - 公开路径（login/health等）始终放行
    """
    if not AUTH_ENABLED:
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

    if not token:
        return JSONResponse(status_code=401, content={"detail": "未登录，请先登录"})

    try:
        payload = verify_jwt_token(token)
        request.state.username = payload["sub"]
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})

    return await call_next(request)
