"""
认证核心模块：密码哈希 + JWT 签发/验证 + 登录限流

密码存储格式（PBKDF2-HMAC-SHA256，自描述字符串，可平滑升级参数）：
    pbkdf2_sha256$<迭代次数>$<base64 salt>$<base64 hash>
旧明文密码仍可校验（常量时间比较），首次成功登录时自动升级为哈希存储。
"""

import base64
import hashlib
import hmac
import secrets
import threading
import time

import jwt

from backend.config.config import JWT_EXPIRY_HOURS, JWT_SECRET_KEY, ROLE_USER

# ====================== 角色定义 ======================
# 规范角色常量定义于 config.py（ROLE_ADMIN / ROLE_MANAGER / ROLE_USER）。
# 此处仅为兼容历史遗留叫法 "member" 做归一化。
_ROLE_ALIASES = {"member": ROLE_USER}


def normalize_role(role: str | None) -> str:
    """将任意角色值归一化为规范角色值（兼容历史 'member'/''，未知值原样保留）"""
    normalized = _ROLE_ALIASES.get(role, role)
    return normalized if normalized else ROLE_USER


# ====================== 密码哈希（PBKDF2-HMAC-SHA256） ======================
_PBKDF2_SCHEME = "pbkdf2_sha256"
# OWASP 推荐迭代次数（2023+）
_PBKDF2_ITERATIONS = 210_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """生成带随机盐的 PBKDF2 密码哈希，返回自描述字符串。"""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return _encode_pbkdf2(salt, digest)


def _encode_pbkdf2(salt: bytes, digest: bytes) -> str:
    return (
        f"{_PBKDF2_SCHEME}${_PBKDF2_ITERATIONS}$"
        + base64.urlsafe_b64encode(salt).rstrip(b"=").decode()
        + "$"
        + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    )


def password_needs_rehash(stored_password: str) -> bool:
    """是否尚未采用哈希存储（旧明文/更早格式）"""
    return bool(stored_password) and not stored_password.startswith(
        _PBKDF2_SCHEME + "$"
    )


def check_password(password: str, stored_password: str) -> bool:
    """验证密码：优先走哈希，兼容旧明文（常量时间比较防时序侧信道）"""
    if not stored_password:
        return False
    if stored_password.startswith(_PBKDF2_SCHEME + "$"):
        return _verify_pbkdf2(password, stored_password)
    return hmac.compare_digest(password, stored_password)


def _verify_pbkdf2(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, hash_b64 = stored.split("$", 3)
        if scheme != _PBKDF2_SCHEME:
            return False
        salt = base64.urlsafe_b64decode(_pad_b64(salt_b64))
        digest = base64.urlsafe_b64decode(_pad_b64(hash_b64))
        iterations = int(iterations)
        if not 1 <= iterations <= 10_000_000:  # 防御畸形配置
            return False
    except (ValueError, TypeError):
        return False
    trial = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(trial, digest)


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


# ====================== 登录限流（进程内滑动窗口） ======================
# 单进程内有效；多进程部署时按进程各自限流，需要更严格可换 Redis 实现。
LOGIN_MAX_FAILURES = 5           # 窗口内允许的最大失败次数
LOGIN_WINDOW_SECONDS = 300       # 滑动窗口（秒）
LOGIN_LOCKOUT_SECONDS = 300      # 超限后的锁定时间（秒）

_login_failures: dict[str, list[float]] = {}
_login_failures_lock = threading.Lock()


def _login_key(client_ip: str, identity: str) -> str:
    return f"{client_ip}|{identity}"


def login_rate_limited(client_ip: str, identity: str) -> bool:
    """是否已触发登录限流。True=应拒绝本次尝试。"""
    key = _login_key(client_ip, identity)
    now = time.monotonic()
    horizon = LOGIN_WINDOW_SECONDS + LOGIN_LOCKOUT_SECONDS
    with _login_failures_lock:
        timestamps = _login_failures.get(key, [])
        timestamps = [t for t in timestamps if now - t < horizon]
        _login_failures[key] = timestamps
        recent = [t for t in timestamps if now - t < LOGIN_WINDOW_SECONDS]
        return len(recent) >= LOGIN_MAX_FAILURES


def record_login_failure(client_ip: str, identity: str) -> None:
    key = _login_key(client_ip, identity)
    now = time.monotonic()
    with _login_failures_lock:
        _login_failures.setdefault(key, []).append(now)


def record_login_success(client_ip: str, identity: str) -> None:
    key = _login_key(client_ip, identity)
    with _login_failures_lock:
        _login_failures.pop(key, None)


# ====================== JWT ======================
def create_jwt_token(
    username: str, is_admin: bool = False, role: str = ROLE_USER
) -> str:
    """签发 JWT 通行证"""
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + JWT_EXPIRY_HOURS * 3600,
        "is_admin": is_admin,
        "role": role,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """验证 JWT 通行证，验证失败抛出异常"""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])