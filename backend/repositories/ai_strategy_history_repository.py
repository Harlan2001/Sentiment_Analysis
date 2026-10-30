"""独立历史会话库，复用项目业务库连接池。"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG
from backend.repositories.base import RecycleBinMixin, RepositoryError, json_default, serialize_row


def _loads_maybe(value: Any) -> Any:
    """消息/版本里的 JSON 列可能是 None、字符串或已解析对象，统一容错。"""
    if value is None or isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _first_clause(text: str | None, limit: int = 48) -> str | None:
    """失败原因只取首句上卡片，完整原因留在详情页。"""
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return None
    positions = [
        cleaned.find(delimiter)
        for delimiter in ("，", "；", "。", "：", "（", "(")
        if delimiter in cleaned
    ]
    if positions:
        cleaned = cleaned[: min(positions)].strip()
    return cleaned[:limit]


def _metric_value(metrics: Any, key: str) -> str | None:
    """从 backtest_metrics_json 的 [{key,label,value}] 里按 key 取原始值。"""
    if not isinstance(metrics, list):
        return None
    for item in metrics:
        if isinstance(item, dict) and item.get("key") == key:
            value = item.get("value")
            return str(value) if value not in (None, "") else None
    return None


def _parse_int_maybe(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def build_conversation_summary(
    conversation: dict[str, Any],
    latest_message: dict[str, Any] | None,
    latest_version: dict[str, Any] | None,
) -> dict[str, Any]:
    """组装列表卡片所需的最近一轮摘要（纯函数，便于单测）。

    标的/模式优先取会话列（新草稿会回写），历史会话退回首条草稿 context_json；
    验收结论取最后一条 assistant 消息，成交/年化取最新版本指标。
    """
    context_raw = (latest_message or {}).get("context_json")
    validation_raw = (latest_message or {}).get("validation_json")
    context = context_raw if isinstance(context_raw, dict) else {}
    validation = validation_raw if isinstance(validation_raw, dict) else {}
    metrics = (latest_version or {}).get("backtest_metrics_json") or []
    status = (latest_message or {}).get("status") or "idle"

    trade_count = validation.get("trade_count")
    if trade_count is None:
        trade_count = _parse_int_maybe(_metric_value(metrics, "total_orders"))
    annual_return = _metric_value(metrics, "compounding_annual_return")

    failure_reason: str | None = None
    if validation.get("verdict") and not validation.get("passed"):
        failure_reason = _first_clause(validation.get("reason"))
    if not failure_reason and status in {"failed", "timed_out"}:
        failure_reason = _first_clause(
            (latest_message or {}).get("public_error_message")
        )

    return {
        "turn_status": status,
        "verdict": validation.get("verdict"),
        "verdict_passed": bool(validation.get("passed")),
        "failure_reason": failure_reason,
        "instrument": conversation.get("instrument") or context.get("instrument"),
        "instrument_code": context.get("instrument_code"),
        "backtest_mode": context.get("backtest_mode"),
        "candle_interval": context.get("candle_interval"),
        "trade_count": trade_count,
        "annual_return": annual_return,
    }


class ArchivedConversationError(RepositoryError):
    """已归档会话不可再写入，避免意外恢复历史策略。"""

    status_code = 409


class GenerationInProgressError(RepositoryError):
    """会话仍有远端生成任务时禁止归档。"""

    status_code = 409


class ConversationNotFoundError(RepositoryError):
    """历史策略会话或消息不存在。"""

    status_code = 404


class AiStrategyHistoryRepository(RecycleBinMixin):
    """AI 策略会话、消息与版本仓储，复用项目业务库连接。

    回收站 CRUD（list_deleted / restore / permanently_delete）继承自
    ``RecycleBinMixin``；``soft_delete_conversation`` 因检查的是子表
    ``ai_strategy_messages`` 的状态（而非会话自身的 ``status``），与前两者不同，
    保留自实现。
    """

    recycle_table = "ai_strategy_conversations"
    recycle_now = "CURRENT_TIMESTAMP"
    recycle_restore_suffix = ", updated_at = CURRENT_TIMESTAMP"
    recycle_list_columns = (
        "id",
        "title",
        "instrument",
        "status",
        "current_local_version_no",
        "last_message_at",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    recycle_not_found = ConversationNotFoundError
    recycle_not_in_trash_msg = "History conversation not found"
    recycle_restore_miss_msg = "恢复策略会话后未找到记录"
    recycle_getter = "get_conversation"

    def __init__(self, settings: dict[str, Any]):
        self._settings = settings

    @classmethod
    def from_environment(cls) -> "AiStrategyHistoryRepository":
        # 独立历史库若配置了 AI_STRATEGY_HISTORY_MYSQL_DATABASE 则用它；
        # 未配置时回退业务库，与建表脚本的目标保持一致
        settings = dict(MYSQL_CONFIG)
        history_db = os.getenv("AI_STRATEGY_HISTORY_MYSQL_DATABASE")
        if history_db:
            settings["database"] = history_db
        return cls(settings)

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

    def warmup(self) -> None:
        """启动预热：跑通一次 TCP/鉴权，让首个用户请求不付连接税。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    def ensure_recycle_bin_schema(self) -> None:
        """Apply the small additive migration in the configured history database."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT COUNT(*) AS count FROM INFORMATION_SCHEMA.COLUMNS
                       WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_strategy_conversations'
                         AND COLUMN_NAME = 'deleted_at'"""
                )
                if int(cursor.fetchone()["count"]) == 0:
                    cursor.execute("ALTER TABLE ai_strategy_conversations ADD COLUMN deleted_at DATETIME NULL")
                    cursor.execute(
                        "CREATE INDEX idx_ai_strategy_conversations_owner_deleted_updated ON ai_strategy_conversations (owner_username, deleted_at, updated_at)"
                    )
            conn.commit()

    def create_conversation(self, owner_username: str, title: str) -> dict[str, Any]:
        title = " ".join(title.split())[:255] or "新策略对话"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ai_strategy_conversations (owner_username, title) VALUES (%s, %s)",
                    (owner_username, title),
                )
                conversation_id = cursor.lastrowid
            conn.commit()
        conversation = self.get_conversation(
            owner_username, conversation_id, include_private=True
        )
        if not conversation:
            raise RuntimeError("创建会话后未找到记录")
        return conversation

    def list_conversations(
        self, owner_username: str, limit: int
    ) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, title, instrument, status, current_local_version_no, last_message_at, created_at, updated_at
                       FROM ai_strategy_conversations WHERE owner_username = %s AND status <> 'archived' AND deleted_at IS NULL
                       ORDER BY updated_at DESC, id DESC LIMIT %s""",
                    (owner_username, limit),
                )
                rows = cursor.fetchall()
                conversations = [serialize_row(row) for row in rows]
                if conversations:
                    latest_messages = self._fetch_latest_assistant_messages(
                        cursor, [item["id"] for item in conversations]
                    )
                    latest_versions = self._fetch_latest_versions(
                        cursor, [item["id"] for item in conversations]
                    )
        for conversation in conversations:
            conversation["summary"] = build_conversation_summary(
                conversation,
                latest_messages.get(conversation["id"]),
                latest_versions.get(conversation["id"]),
            )
        return conversations

    @staticmethod
    def _fetch_latest_assistant_messages(
        cursor: Any, conversation_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """每个会话最后一条 assistant 消息（草稿/运行中/终态都看它），一次批量取。"""
        placeholders = ",".join(["%s"] * len(conversation_ids))
        cursor.execute(
            f"""SELECT m.conversation_id, m.status, m.validation_json,
                              m.public_error_message, m.context_json
                         FROM ai_strategy_messages m
                         JOIN (
                               SELECT conversation_id, MAX(sequence_no) AS max_sequence
                                 FROM ai_strategy_messages
                                WHERE conversation_id IN ({placeholders}) AND role = 'assistant'
                                GROUP BY conversation_id
                         ) latest ON latest.conversation_id = m.conversation_id
                                AND latest.max_sequence = m.sequence_no""",
            conversation_ids,
        )
        return {
            int(row["conversation_id"]): {
                "status": row["status"],
                "validation_json": _loads_maybe(row.get("validation_json")),
                "public_error_message": row.get("public_error_message"),
                "context_json": _loads_maybe(row.get("context_json")) or {},
            }
            for row in cursor.fetchall()
        }

    @staticmethod
    def _fetch_latest_versions(
        cursor: Any, conversation_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """每个会话最新版本的指标摘要，供列表卡片直接展示核心数字。"""
        placeholders = ",".join(["%s"] * len(conversation_ids))
        cursor.execute(
            f"""SELECT v.conversation_id, v.local_version_no, v.backtest_metrics_json
                         FROM ai_strategy_versions v
                         JOIN (
                               SELECT conversation_id, MAX(local_version_no) AS max_version
                                 FROM ai_strategy_versions
                                WHERE conversation_id IN ({placeholders})
                                GROUP BY conversation_id
                         ) latest ON latest.conversation_id = v.conversation_id
                                AND latest.max_version = v.local_version_no""",
            conversation_ids,
        )
        return {
            int(row["conversation_id"]): {
                "local_version_no": row["local_version_no"],
                "backtest_metrics_json": _loads_maybe(
                    row.get("backtest_metrics_json")
                )
                or [],
            }
            for row in cursor.fetchall()
        }

    def get_conversation(
        self,
        owner_username: str,
        conversation_id: int,
        *,
        include_private: bool = False,
    ) -> dict[str, Any] | None:
        columns = "id, owner_username, title, instrument, status, current_local_version_no, last_message_at, created_at, updated_at"
        if include_private:
            columns += ", remote_template_id, remote_session_id"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT {columns} FROM ai_strategy_conversations WHERE id = %s AND owner_username = %s AND deleted_at IS NULL",
                    (conversation_id, owner_username),
                )
                row = cursor.fetchone()
        return serialize_row(row) if row else None

    def create_prompt_draft(
        self,
        owner_username: str,
        conversation_id: int,
        requirement: str,
        system_draft_prompt: str,
        context_snapshot: dict[str, Any],
        instrument_label: str | None = None,
    ) -> dict[str, int]:
        """Save a user request and a non-remote draft awaiting confirmation."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM ai_strategy_conversations WHERE id = %s AND owner_username = %s FOR UPDATE",
                    (conversation_id, owner_username),
                )
                conversation = cursor.fetchone()
                if not conversation:
                    raise ConversationNotFoundError("History conversation not found")
                if conversation["status"] != "active":
                    raise ArchivedConversationError("Archived conversations cannot be continued")
                cursor.execute(
                    "SELECT id FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s AND status IN ('running', 'pending_confirmation') LIMIT 1",
                    (conversation_id, owner_username),
                )
                if cursor.fetchone():
                    raise GenerationInProgressError(
                        "Confirm or wait for the current strategy turn first"
                    )
                cursor.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) AS last_sequence FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s",
                    (conversation_id, owner_username),
                )
                sequence_no = int(cursor.fetchone()["last_sequence"])
                cursor.execute(
                    """INSERT INTO ai_strategy_messages (conversation_id, owner_username, sequence_no, role, content, status)
                                  VALUES (%s, %s, %s, 'user', %s, 'succeeded')""",
                    (conversation_id, owner_username, sequence_no + 1, requirement),
                )
                user_message_id = cursor.lastrowid
                cursor.execute(
                    """INSERT INTO ai_strategy_messages (
                                      conversation_id, owner_username, sequence_no, role, content, status,
                                      generated_prompt, system_draft_prompt, references_json, context_json
                                  ) VALUES (%s, %s, %s, 'assistant', %s, 'pending_confirmation', %s, %s, %s, %s)""",
                    (
                        conversation_id,
                        owner_username,
                        sequence_no + 2,
                        "\u5df2\u6839\u636e\u4f60\u7684\u9700\u6c42\u3001\u5f53\u524d\u6807\u7684\u8303\u56f4\u548c\u672c\u8f6e\u76f8\u5173\u65b0\u95fb\u751f\u6210\u7b56\u7565\u63d0\u793a\u8bcd\u3002\u8bf7\u5728\u53f3\u4fa7\u68c0\u67e5\u6216\u4fee\u6539\uff0c\u786e\u8ba4\u65e0\u8bef\u540e\u70b9\u51fb\u2018\u786e\u8ba4\u53d1\u9001\u5e76\u751f\u6210\u7b56\u2019\u3002",
                        system_draft_prompt,
                        system_draft_prompt,
                        json.dumps(
                            context_snapshot.get("references", []),
                            ensure_ascii=False,
                            default=json_default,
                        ),
                        json.dumps(
                            context_snapshot, ensure_ascii=False, default=json_default
                        ),
                    ),
                )
                assistant_message_id = cursor.lastrowid
                conversation_updates = (
                    "last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP"
                )
                conversation_params: tuple[Any, ...] = (conversation_id, owner_username)
                if instrument_label:
                    # 该列历史上恒 NULL；现在记下本轮任务卡实际定下的标的，
                    # 让会话列表能直接展示交易品种。
                    conversation_updates = (
                        "instrument = %s, last_message_at = CURRENT_TIMESTAMP, "
                        "updated_at = CURRENT_TIMESTAMP"
                    )
                    conversation_params = (
                        instrument_label[:255],
                        conversation_id,
                        owner_username,
                    )
                cursor.execute(
                    f"UPDATE ai_strategy_conversations SET {conversation_updates} WHERE id = %s AND owner_username = %s",
                    conversation_params,
                )
            conn.commit()
        return {
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }

    def get_prompt_draft(
        self, owner_username: str, conversation_id: int, assistant_message_id: int
    ) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT assistant.id, assistant.status, assistant.system_draft_prompt, assistant.context_json,
                                         user_message.content AS user_requirement
                                  FROM ai_strategy_messages AS assistant
                                  JOIN ai_strategy_messages AS user_message
                                    ON user_message.conversation_id = assistant.conversation_id
                                   AND user_message.sequence_no = assistant.sequence_no - 1
                                   AND user_message.role = 'user'
                                  WHERE assistant.id = %s AND assistant.conversation_id = %s
                                    AND assistant.owner_username = %s AND assistant.role = 'assistant'""",
                    (assistant_message_id, conversation_id, owner_username),
                )
                row = cursor.fetchone()
        return serialize_row(row) if row else None

    def abandon_prompt_draft(
        self,
        owner_username: str,
        conversation_id: int,
        assistant_message_id: int,
    ) -> bool:
        """放弃待确认草稿：置 cancelled，让会话可以重新 draft。

        协议没有取消命令，但待确认阶段本来就没有任何远端调用，放弃是纯本地操作。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_messages
                                  SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s
                                    AND role = 'assistant' AND status = 'pending_confirmation'""",
                    (assistant_message_id, conversation_id, owner_username),
                )
                abandoned = cursor.rowcount == 1
                if abandoned:
                    cursor.execute(
                        "UPDATE ai_strategy_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                        (conversation_id, owner_username),
                    )
            conn.commit()
        return abandoned

    def confirm_prompt_draft(
        self,
        owner_username: str,
        conversation_id: int,
        assistant_message_id: int,
        user_edited_prompt: str,
        final_sent_prompt: str,
    ) -> bool:
        """Make a saved draft immutable and mark it running immediately before remote I/O."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_messages
                                  SET user_edited_prompt = %s, final_sent_prompt = %s, generated_prompt = %s,
                                      status = 'running', updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s
                                    AND role = 'assistant' AND status = 'pending_confirmation'""",
                    (
                        user_edited_prompt,
                        final_sent_prompt,
                        final_sent_prompt,
                        assistant_message_id,
                        conversation_id,
                        owner_username,
                    ),
                )
                confirmed = cursor.rowcount == 1
                if confirmed:
                    cursor.execute(
                        "UPDATE ai_strategy_conversations SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                        (conversation_id, owner_username),
                    )
            conn.commit()
        return confirmed

    def save_remote_session(
        self,
        owner_username: str,
        conversation_id: int,
        template_id: str,
        session_id: str,
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_conversations SET remote_template_id = %s, remote_session_id = %s, updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND owner_username = %s""",
                    (template_id, session_id, conversation_id, owner_username),
                )
                if cursor.rowcount != 1:
                    raise ConversationNotFoundError("History conversation not found")
            conn.commit()

    def complete_generation(
        self,
        owner_username: str,
        conversation_id: int,
        assistant_message_id: int,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Persist the remote answer and its strategy version in one transaction."""
        strategy = result.get("strategy")
        has_strategy_code = bool(strategy and str(strategy.get("code") or "").strip())
        message_status = "succeeded" if has_strategy_code else "failed"
        public_error = (
            None
            if has_strategy_code
            else "DreamStrategy did not create a complete strategy artifact. Please retry generation."
        )
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT current_local_version_no FROM ai_strategy_conversations WHERE id = %s AND owner_username = %s FOR UPDATE",
                    (conversation_id, owner_username),
                )
                conversation = cursor.fetchone()
                if not conversation:
                    raise ConversationNotFoundError("History conversation not found")
                cursor.execute(
                    """UPDATE ai_strategy_messages SET content = %s, status = %s, public_error_message = %s, remote_message_id = %s, elapsed_seconds = %s, validation_json = %s, updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s""",
                    (
                        result.get("summary", ""),
                        message_status,
                        public_error,
                        result.get("message_id") or None,
                        result.get("elapsed_seconds"),
                        # 验收结论单独成列：它和平台口径的 backtest_passed 语义不同，
                        # 混在一个字段里会让前端无法区分"跑完了"和"真的成交了"。
                        (
                            json.dumps(result["validation"], ensure_ascii=False)
                            if result.get("validation")
                            else None
                        ),
                        assistant_message_id,
                        conversation_id,
                        owner_username,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ConversationNotFoundError("History conversation not found")
                version = None
                if has_strategy_code:
                    local_version_no = int(conversation["current_local_version_no"]) + 1
                    cursor.execute(
                        """INSERT INTO ai_strategy_versions (conversation_id, owner_username, source_message_id, local_version_no, remote_template_version_id, remote_template_version_no, name, description, code, backtest_passed, backtest_exit_code, backtest_summary, backtest_metrics_json)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            conversation_id,
                            owner_username,
                            assistant_message_id,
                            local_version_no,
                            result.get("template_version_id") or None,
                            result.get("template_version_no") or None,
                            strategy.get("name", ""),
                            strategy.get("description", ""),
                            strategy.get("code", ""),
                            result.get("backtest_passed"),
                            result.get("backtest_exit_code"),
                            result.get("backtest_summary", ""),
                            json.dumps(
                                result.get("backtest_metrics", []), ensure_ascii=False
                            ),
                        ),
                    )
                    version_id = cursor.lastrowid
                    cursor.execute(
                        "UPDATE ai_strategy_conversations SET current_local_version_no = %s, last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                        (local_version_no, conversation_id, owner_username),
                    )
                    cursor.execute(
                        """SELECT id, source_message_id, local_version_no, remote_template_version_id, remote_template_version_no, name, description, code, backtest_passed, backtest_exit_code, backtest_summary, backtest_metrics_json, created_at
                                      FROM ai_strategy_versions WHERE id = %s""",
                        (version_id,),
                    )
                    version = serialize_row(cursor.fetchone())
            conn.commit()
        return version

    def fail_generation(
        self,
        owner_username: str,
        conversation_id: int,
        assistant_message_id: int,
        message: str,
        *,
        timed_out: bool = False,
    ) -> None:
        status = "timed_out" if timed_out else "failed"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_messages SET content = %s, public_error_message = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s""",
                    (
                        message,
                        message,
                        status,
                        assistant_message_id,
                        conversation_id,
                        owner_username,
                    ),
                )
                cursor.execute(
                    "UPDATE ai_strategy_conversations SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                    (conversation_id, owner_username),
                )
            conn.commit()

    def sweep_stale_running(self, owner_username: str, conversation_id: int) -> None:
        """Flip any ``running`` message stuck for >16 minutes to ``timed_out``.

        Async background generations can be lost when the process restarts mid-run;
        without this sweep a stale ``running`` row would block the conversation
        forever (``create_prompt_draft`` refuses while one exists).
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_messages SET status = 'timed_out', content = 'DreamStrategy generation timed out; retry this conversation.', public_error_message = 'DreamStrategy generation timed out; retry this conversation.', updated_at = CURRENT_TIMESTAMP
                                  WHERE conversation_id = %s AND owner_username = %s AND status = 'running' AND updated_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 16 MINUTE)""",
                    (conversation_id, owner_username),
                )
            conn.commit()

    def get_conversation_detail(
        self, owner_username: str, conversation_id: int
    ) -> dict[str, Any] | None:
        conversation = self.get_conversation(owner_username, conversation_id)
        if not conversation:
            return None
        self.sweep_stale_running(owner_username, conversation_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, sequence_no, role, content, status, generated_prompt, system_draft_prompt, user_edited_prompt, final_sent_prompt, references_json, context_json, validation_json, public_error_message, remote_message_id, elapsed_seconds, created_at, updated_at
                                  FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s ORDER BY sequence_no ASC""",
                    (conversation_id, owner_username),
                )
                messages = [serialize_row(row) for row in cursor.fetchall()]
                cursor.execute(
                    """SELECT id, source_message_id, local_version_no, remote_template_version_id, remote_template_version_no, name, description, code, backtest_passed, backtest_exit_code, backtest_summary, backtest_metrics_json, created_at
                                  FROM ai_strategy_versions WHERE conversation_id = %s AND owner_username = %s ORDER BY local_version_no DESC""",
                    (conversation_id, owner_username),
                )
                versions = [serialize_row(row) for row in cursor.fetchall()]
        return {
            "conversation": conversation,
            "messages": messages,
            "versions": versions,
        }

    def archive_conversation(self, owner_username: str, conversation_id: int) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM ai_strategy_conversations WHERE id = %s AND owner_username = %s FOR UPDATE",
                    (conversation_id, owner_username),
                )
                conversation = cursor.fetchone()
                if not conversation or conversation["status"] != "active":
                    return False
                cursor.execute(
                    "SELECT id FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s AND status = 'running' LIMIT 1",
                    (conversation_id, owner_username),
                )
                if cursor.fetchone():
                    raise GenerationInProgressError(
                        "Wait for the running generation before archiving"
                    )
                cursor.execute(
                    "UPDATE ai_strategy_conversations SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                    (conversation_id, owner_username),
                )
                archived = cursor.rowcount == 1
            conn.commit()
        return archived

    def list_deleted_conversations(self, owner_username: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_deleted_tasks(owner_username, limit)

    def soft_delete_conversation(self, owner_username: str, conversation_id: int) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM ai_strategy_conversations WHERE id = %s AND owner_username = %s AND deleted_at IS NULL FOR UPDATE",
                    (conversation_id, owner_username),
                )
                if not cursor.fetchone():
                    raise ConversationNotFoundError("History conversation not found")
                cursor.execute(
                    """SELECT id FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s
                       AND status IN ('running', 'pending_confirmation') LIMIT 1""",
                    (conversation_id, owner_username),
                )
                if cursor.fetchone():
                    raise GenerationInProgressError("进行中的策略生成任务不能删除")
                cursor.execute(
                    "UPDATE ai_strategy_conversations SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                    (conversation_id, owner_username),
                )
            conn.commit()
        return {"deleted": True}

    def restore_conversation(self, owner_username: str, conversation_id: int) -> dict[str, Any]:
        return self.restore_task(owner_username, conversation_id)

    def permanently_delete_conversation(self, owner_username: str, conversation_id: int) -> dict[str, bool]:
        return self.permanently_delete_task(owner_username, conversation_id)

    def permanently_delete_all_deleted_conversations(self, owner_username: str) -> int:
        return self.permanently_delete_all_deleted_tasks(owner_username)
