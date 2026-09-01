"""Authentication endpoints, reusing the existing ``users`` table."""

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.auth.auth import (
    check_password,
    create_jwt_token,
    hash_password,
    login_rate_limited,
    normalize_role,
    password_needs_rehash,
    record_login_failure,
    record_login_success,
    verify_jwt_token,
)
from backend.auth.dependencies import extract_bearer_token
from backend.common.database import get_connection
from backend.config.config import (
    API_PREFIX,
    AUTH_ENABLED,
    AUTH_PHONE_LOGIN,
    ROLE_ADMIN,
)

router = APIRouter(prefix=f"{API_PREFIX}/auth", tags=["auth"])

_RATE_LIMIT_MESSAGE = "尝试过于频繁，请稍后再试"
_PHONE_GENERIC_FAILURE = "手机号未注册或已停用"


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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _response(user_id, username, display_name, is_admin, db_role) -> LoginResponse:
    role = ROLE_ADMIN if is_admin else normalize_role(db_role)
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
def login(request: Request, body: LoginRequest):
    if not AUTH_ENABLED:
        return LoginResponse(success=True, message="免登录模式已启用")
    client_ip = _client_ip(request)
    if login_rate_limited(client_ip, body.username):
        raise HTTPException(status_code=429, detail=_RATE_LIMIT_MESSAGE)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, password, display_name, is_active,
                          COALESCE(is_admin, 0), COALESCE(NULLIF(role, ''), 'user')
                   FROM users WHERE username = %s""",
                (body.username,),
            )
            row = cursor.fetchone()
        if not row or not check_password(body.password, row[2]):
            record_login_failure(client_ip, body.username)
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not row[4]:
            raise HTTPException(status_code=403, detail="账户已被禁用")
        # 旧明文密码首次成功登录时升级为哈希存储
        if password_needs_rehash(row[2]):
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password = %s WHERE id = %s",
                    (hash_password(body.password), row[0]),
                )
            conn.commit()
        record_login_success(client_ip, body.username)
        return _response(row[0], row[1], row[3], row[5], row[6])
    finally:
        conn.close()


@router.post("/login/phone", response_model=LoginResponse)
def login_by_phone(request: Request, body: PhoneLoginRequest):
    if not AUTH_ENABLED:
        return LoginResponse(success=True, message="免登录模式已启用")
    if not AUTH_PHONE_LOGIN:
        raise HTTPException(
            status_code=403, detail="手机号登录未启用，请使用账号密码登录"
        )
    client_ip = _client_ip(request)
    phone_identity = f"phone:{body.phone}"
    if login_rate_limited(client_ip, phone_identity):
        raise HTTPException(status_code=429, detail=_RATE_LIMIT_MESSAGE)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, display_name, is_active,
                          COALESCE(is_admin, 0), COALESCE(NULLIF(role, ''), 'user')
                   FROM users WHERE phone = %s""",
                (body.phone,),
            )
            row = cursor.fetchone()
        # 统一报错信息，避免枚举已注册手机号
        if not row:
            record_login_failure(client_ip, phone_identity)
            raise HTTPException(status_code=401, detail=_PHONE_GENERIC_FAILURE)
        if not row[3]:
            raise HTTPException(status_code=403, detail="账户已被禁用")
        record_login_success(client_ip, phone_identity)
        return _response(row[0], row[1], row[2], row[4], row[5])
    finally:
        conn.close()


def _current_identity(username: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, display_name, is_active,
                          COALESCE(is_admin, 0), COALESCE(NULLIF(role, ''), 'user')
                   FROM users WHERE username = %s""",
                (username,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        db_role = row[5]
        is_admin = bool(row[4])
        role = ROLE_ADMIN if is_admin else normalize_role(db_role)
        return {
            "id": str(row[0]),
            "username": row[1],
            "display_name": row[2] or row[1],
            "is_active": bool(row[3]),
            "role": role,
        }
    finally:
        conn.close()


@router.get("/status")
def auth_status(request: Request):
    if not AUTH_ENABLED:
        return {
            "auth_enabled": False,
            "authenticated": True,
            "is_admin": True,
            "role": ROLE_ADMIN,
            "user_id": None,
        }
    token = extract_bearer_token(request)
    if not token:
        return {"auth_enabled": True, "authenticated": False}
    try:
        payload = verify_jwt_token(token)
    except jwt.InvalidTokenError:
        return {"auth_enabled": True, "authenticated": False}
    identity = _current_identity(payload.get("sub") or "")
    if not identity or not identity["is_active"]:
        return {"auth_enabled": True, "authenticated": False}
    return {
        "auth_enabled": True,
        "authenticated": True,
        "username": identity["username"],
        "display_name": identity["display_name"],
        "is_admin": identity["role"] == ROLE_ADMIN,
        "role": identity["role"],
        "user_id": identity["id"],
    }


@router.get("/me")
def current_user(request: Request):
    username = getattr(request.state, "username", "")
    identity = _current_identity(username) if username else None
    if not identity:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"data": {**identity, "authenticated": True}}