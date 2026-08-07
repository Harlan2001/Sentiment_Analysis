"""通过旧认证状态接口解析当前用户。"""

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.integrations.legacy_api import LegacyApiError


PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def auth_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs") or request.method == "OPTIONS":
        return await call_next(request)
    try:
        user = await request.app.state.legacy_api.get_current_user(request.headers.get("Authorization"))
    except LegacyApiError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": str(exc), "details": {}}})
    request.state.workbench_user = user
    request.state.username = user["username"]
    return await call_next(request)
