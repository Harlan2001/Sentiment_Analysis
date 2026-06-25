"""
认证核心模块：密码验证 + JWT 签发/验证
明文密码版：直接比对，不哈希
"""
import time

import jwt

from backend.config.config import JWT_SECRET_KEY, JWT_EXPIRY_HOURS


def check_password(password: str, stored_password: str) -> bool:
    """验证密码（明文比对）"""
    return password == stored_password


def create_jwt_token(username: str) -> str:
    """签发 JWT 通行证"""
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + JWT_EXPIRY_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """验证 JWT 通行证，验证失败抛出异常"""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
