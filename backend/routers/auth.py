"""Authentication endpoints, reusing the existing ``users`` table."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.auth.auth import check_password, create_jwt_token, verify_jwt_token
from backend.common.database import get_connection
from backend.config.config import API_PREFIX, AUTH_ENABLED

router = APIRouter(prefix=f"{API_PREFIX}/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class PhoneLoginRequest(BaseModel):
    phone: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    username: str | None = None
    display_name: str | None = None
    is_admin: bool = False
    role: str = "member"
    user_id: str | None = None
    message: str = ""


def _response(user_id, username, display_name, is_admin) -> LoginResponse:
    role = "admin" if is_admin else "member"
    return LoginResponse(
        success=True,
        token=create_jwt_token(username, bool(is_admin), role),
        username=username,
        display_name=display_name or username,
        is_admin=bool(is_admin),
        role=role,
        user_id=str(user_id),
        message="登录成功",
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if not AUTH_ENABLED:
        return LoginResponse(success=True, message="免登录模式已启用")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, password, display_name, is_active, COALESCE(is_admin, 0)
                   FROM users WHERE username = %s""",
                (body.username,),
            )
            row = cursor.fetchone()
        if not row or not check_password(body.password, row[2]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not row[4]:
            raise HTTPException(status_code=403, detail="账户已被禁用")
        return _response(row[0], row[1], row[3], row[5])
    finally:
        conn.close()


@router.post("/login/phone", response_model=LoginResponse)
def login_by_phone(body: PhoneLoginRequest):
    if not AUTH_ENABLED:
        return LoginResponse(success=True, message="免登录模式已启用")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, display_name, is_active, COALESCE(is_admin, 0)
                   FROM users WHERE phone = %s""",
                (body.phone,),
            )
            row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="手机号未注册")
        if not row[3]:
            raise HTTPException(status_code=403, detail="账户已被禁用")
        return _response(row[0], row[1], row[2], row[4])
    finally:
        conn.close()


def _current_identity(username: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, display_name, is_active, COALESCE(is_admin, 0) FROM users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]), "username": row[1], "display_name": row[2] or row[1],
            "is_active": bool(row[3]), "role": "admin" if row[4] else "member",
        }
    finally:
        conn.close()


@router.get("/status")
def auth_status(request: Request):
    if not AUTH_ENABLED:
        return {"auth_enabled": False, "authenticated": True, "is_admin": True, "role": "admin", "user_id": None}
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"auth_enabled": True, "authenticated": False}
    try:
        payload = verify_jwt_token(auth_header.split(" ", 1)[1])
        identity = _current_identity(payload["sub"])
        if not identity or not identity["is_active"]:
            return {"auth_enabled": True, "authenticated": False}
        return {"auth_enabled": True, "authenticated": True, "username": identity["username"], "display_name": identity["display_name"], "is_admin": identity["role"] == "admin", "role": identity["role"], "user_id": identity["id"]}
    except Exception:
        return {"auth_enabled": True, "authenticated": False}


@router.get("/me")
def current_user(request: Request):
    username = getattr(request.state, "username", "")
    identity = _current_identity(username) if username else None
    if not identity:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"data": {**identity, "authenticated": True}}
