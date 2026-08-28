from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import pymysql
from cryptography.fernet import Fernet, InvalidToken
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG


class FeishuConnectionError(RuntimeError):
    pass


def _token_cipher() -> Fernet:
    raw_key = os.getenv("FEISHU_TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        raise FeishuConnectionError(
            "飞书连接尚未配置 FEISHU_TOKEN_ENCRYPTION_KEY，无法安全保存授权令牌。"
        )
    try:
        return Fernet(raw_key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise FeishuConnectionError(
            "FEISHU_TOKEN_ENCRYPTION_KEY 必须是 Fernet.generate_key() 生成的密钥。"
        ) from exc


class FeishuConnectionRepository:
    """Persistence for per-user Feishu OAuth connections."""

    def __init__(self, settings: dict[str, Any] | None = None):
        self._settings = settings or dict(MYSQL_CONFIG)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        connection = pymysql.connect(
            **{**self._settings, "autocommit": False}, cursorclass=DictCursor
        )
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_oauth_state(self, username: str) -> str:
        state = secrets.token_urlsafe(32)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_feishu_oauth_states
                       (state_hash, username, expires_at) VALUES (%s, %s, %s)""",
                    (self._hash_state(state), username, datetime.now(timezone.utc) + timedelta(minutes=10)),
                )
            conn.commit()
        return state

    def consume_oauth_state(self, state: str) -> str | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT username FROM workbench_feishu_oauth_states
                       WHERE state_hash = %s AND expires_at > UTC_TIMESTAMP()""",
                    (self._hash_state(state),),
                )
                row = cursor.fetchone()
                cursor.execute(
                    "DELETE FROM workbench_feishu_oauth_states WHERE state_hash = %s",
                    (self._hash_state(state),),
                )
            conn.commit()
        return row["username"] if row else None

    def get_connection(self, username: str, include_tokens: bool = False) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT username, feishu_user_id, tenant_key, scopes, expires_at,
                              connected_at, last_used_at, access_token, refresh_token
                       FROM workbench_feishu_connections WHERE username = %s""",
                    (username,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        row["scopes"] = row["scopes"] or []
        if isinstance(row["scopes"], str):
            import json
            row["scopes"] = json.loads(row["scopes"])
        if include_tokens:
            cipher = _token_cipher()
            try:
                row["access_token"] = cipher.decrypt(row["access_token"].encode()).decode()
                row["refresh_token"] = cipher.decrypt(row["refresh_token"].encode()).decode()
            except InvalidToken as exc:
                raise FeishuConnectionError("已保存的飞书令牌无法解密，请重新连接。") from exc
        else:
            row.pop("access_token", None)
            row.pop("refresh_token", None)
        return row

    def upsert_connection(self, username: str, token_data: dict[str, Any]) -> None:
        import json

        cipher = _token_cipher()
        access_token = str(token_data["access_token"])
        refresh_token = str(token_data["refresh_token"])
        expires_in = max(int(token_data.get("expires_in") or 7200), 60)
        scopes = token_data.get("scopes") or []
        if isinstance(scopes, str):
            scopes = scopes.split()
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_feishu_connections
                       (username, feishu_user_id, tenant_key, scopes, access_token, refresh_token, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND))
                         ON DUPLICATE KEY UPDATE feishu_user_id=COALESCE(VALUES(feishu_user_id), feishu_user_id), tenant_key=COALESCE(VALUES(tenant_key), tenant_key),
                         scopes=VALUES(scopes), access_token=VALUES(access_token), refresh_token=VALUES(refresh_token),
                         expires_at=VALUES(expires_at), connected_at=UTC_TIMESTAMP(), last_used_at=NULL""",
                    (
                        username,
                        token_data.get("open_id") or token_data.get("user_id"),
                        token_data.get("tenant_key"),
                        json.dumps(scopes, ensure_ascii=False),
                        cipher.encrypt(access_token.encode()).decode(),
                        cipher.encrypt(refresh_token.encode()).decode(),
                        expires_in,
                    ),
                )
            conn.commit()

    def delete_connection(self, username: str) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                count = cursor.execute(
                    "DELETE FROM workbench_feishu_connections WHERE username = %s", (username,)
                )
            conn.commit()
        return bool(count)

    def touch_connection(self, username: str) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE workbench_feishu_connections SET last_used_at=UTC_TIMESTAMP() WHERE username=%s",
                    (username,),
                )
            conn.commit()

    def audit(self, username: str, tool_name: str, success: bool, detail: str | None = None) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_feishu_mcp_audit_logs (username, tool_name, success, detail)
                       VALUES (%s, %s, %s, %s)""",
                    (username, tool_name, success, (detail or "")[:500]),
                )
            conn.commit()

    @staticmethod
    def _hash_state(state: str) -> str:
        return hashlib.sha256(state.encode()).hexdigest()
