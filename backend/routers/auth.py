"""
认证路由：登录、状态查询
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.auth.auth import check_password, create_jwt_token, verify_jwt_token
from backend.common.database import get_connection
from backend.config.config import API_PREFIX, AUTH_ENABLED

router = APIRouter(prefix=f"{API_PREFIX}/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    username: str | None = None
    display_name: str | None = None
    message: str = ""


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """用户登录"""
    if not AUTH_ENABLED:
        return LoginResponse(
            success=True,
            message="免登录模式已启用",
        )

    # 查询用户（明文密码，直接比对）
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username, password, display_name, is_active FROM users WHERE username = %s",
                (body.username,),
            )
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        username, stored_password, display_name, is_active = row
        if not is_active:
            raise HTTPException(status_code=403, detail="账户已被禁用")

        if not check_password(body.password, stored_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_jwt_token(username)
        return LoginResponse(
            success=True,
            token=token,
            username=username,
            display_name=display_name or username,
            message="登录成功",
        )
    finally:
        conn.close()


@router.get("/status")
def auth_status(request: Request):
    """
    返回当前认证状态。
    前端用此接口判断是否需要显示登录页面。
    """
    if not AUTH_ENABLED:
        return {
            "auth_enabled": False,
            "authenticated": True,
        }

    # 检查当前请求是否带有有效 token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {
            "auth_enabled": True,
            "authenticated": False,
        }

    try:
        token = auth_header.split(" ", 1)[1]
        payload = verify_jwt_token(token)
        return {
            "auth_enabled": True,
            "authenticated": True,
            "username": payload["sub"],
        }
    except Exception:
        return {
            "auth_enabled": True,
            "authenticated": False,
        }
