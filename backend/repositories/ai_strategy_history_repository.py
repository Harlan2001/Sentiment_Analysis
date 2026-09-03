"""独立历史会话库，复用项目业务库连接池。"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG
from backend.repositories.base import RecycleBinMixin, json_default, serialize_row


class ArchivedConversationError(RuntimeError):
    """已归档会话不可再写入，避免意外恢复历史策略。"""


class GenerationInProgressError(RuntimeError):
    """会话仍有远端生成任务时禁止归档。"""


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
    recycle_not_found = KeyError
    recycle_not_in_trash_msg = "conversation_not_found"
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
        return [serialize_row(row) for row in rows]

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
                    raise KeyError("conversation_not_found")
                if conversation["status"] != "active":
                    raise ArchivedConversationError("conversation_archived")
                cursor.execute(
                    "SELECT id FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s AND status IN ('running', 'pending_confirmation') LIMIT 1",
                    (conversation_id, owner_username),
                )
                if cursor.fetchone():
                    raise GenerationInProgressError(
                        "generation_or_confirmation_in_progress"
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
                cursor.execute(
                    "UPDATE ai_strategy_conversations SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND owner_username = %s",
                    (conversation_id, owner_username),
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

    def replace_prompt_draft(
        self,
        owner_username: str,
        conversation_id: int,
        assistant_message_id: int,
        system_draft_prompt: str,
        context_snapshot: dict[str, Any],
    ) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE ai_strategy_messages
                                  SET generated_prompt = %s, system_draft_prompt = %s, user_edited_prompt = NULL,
                                      final_sent_prompt = NULL, references_json = %s, context_json = %s,
                                      updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s
                                    AND role = 'assistant' AND status = 'pending_confirmation'""",
                    (
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
                        assistant_message_id,
                        conversation_id,
                        owner_username,
                    ),
                )
                updated = cursor.rowcount == 1
            conn.commit()
        return updated

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
                    raise KeyError("conversation_not_found")
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
                    raise KeyError("conversation_not_found")
                cursor.execute(
                    """UPDATE ai_strategy_messages SET content = %s, status = %s, public_error_message = %s, remote_message_id = %s, elapsed_seconds = %s, updated_at = CURRENT_TIMESTAMP
                                  WHERE id = %s AND conversation_id = %s AND owner_username = %s""",
                    (
                        result.get("summary", ""),
                        message_status,
                        public_error,
                        result.get("message_id") or None,
                        result.get("elapsed_seconds"),
                        assistant_message_id,
                        conversation_id,
                        owner_username,
                    ),
                )
                if cursor.rowcount != 1:
                    raise KeyError("assistant_message_not_found")
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
                    """SELECT id, sequence_no, role, content, status, generated_prompt, system_draft_prompt, user_edited_prompt, final_sent_prompt, references_json, context_json, public_error_message, created_at, updated_at
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
                    raise GenerationInProgressError("generation_in_progress")
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
                    raise KeyError("conversation_not_found")
                cursor.execute(
                    """SELECT id FROM ai_strategy_messages WHERE conversation_id = %s AND owner_username = %s
                       AND status IN ('running', 'pending_confirmation') LIMIT 1""",
                    (conversation_id, owner_username),
                )
                if cursor.fetchone():
                    raise GenerationInProgressError("generation_in_progress")
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
