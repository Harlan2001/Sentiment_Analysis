"""Minimal user-management endpoints backed by the existing users table."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.auth.auth import hash_password
from backend.common.database import get_connection
from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/workbench/users", tags=["workspace-users"])


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=120)
    role: str = "member"

    @field_validator("username", "display_name")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cannot be empty")
        return value


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = None
    is_active: bool | None = None


def _as_user(row: tuple) -> dict:
    user_id, username, display_name, is_active, is_admin = row
    return {
        "id": str(user_id),
        "username": username,
        "display_name": display_name or username,
        "role": "admin" if is_admin else "member",
        "is_active": bool(is_active),
    }


def _require_admin(request: Request) -> None:
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(status_code=403, detail="Administrator access required")


@router.get("")
def list_users(request: Request):
    _require_admin(request)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, display_name, is_active, COALESCE(is_admin, 0) FROM users ORDER BY username")
            rows = cursor.fetchall()
        return {"data": {"items": [_as_user(row) for row in rows]}}
    finally:
        conn.close()


@router.post("", status_code=201)
def create_user(request: Request, body: UserCreateRequest):
    _require_admin(request)
    is_admin = body.role == "admin"
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (body.username,))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="Username already exists")
            cursor.execute(
                """INSERT INTO users (username, password, display_name, is_active, is_admin, role)
                   VALUES (%s, %s, %s, 1, %s, %s)""",
                (body.username, hash_password(body.password), body.display_name, is_admin, "admin" if is_admin else "user"),
            )
            user_id = cursor.lastrowid
            cursor.execute("SELECT id, username, display_name, is_active, COALESCE(is_admin, 0) FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
        conn.commit()
        return {"data": _as_user(row)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/{user_id}")
def update_user(request: Request, user_id: int, body: UserUpdateRequest):
    _require_admin(request)
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied")
    fields: list[str] = []
    params: list[object] = []
    if "display_name" in changes:
        fields.append("display_name = %s")
        params.append(changes["display_name"].strip())
    if "is_active" in changes:
        fields.append("is_active = %s")
        params.append(changes["is_active"])
    if "role" in changes:
        is_admin = changes["role"] == "admin"
        fields.extend(["is_admin = %s", "role = %s"])
        params.extend([is_admin, "admin" if is_admin else "user"])
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", (*params, user_id))
            if cursor.rowcount != 1:
                raise HTTPException(status_code=404, detail="User not found")
            cursor.execute("SELECT id, username, display_name, is_active, COALESCE(is_admin, 0) FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
        conn.commit()
        return {"data": _as_user(row)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
