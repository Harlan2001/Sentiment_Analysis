"""政策文件仓储：上传文件与分析结果的读写。

与研报仓储同构：按 (owner, file_hash) 去重，分析结果与文件一对一。
"""

from __future__ import annotations

import json
from typing import Any

from backend.repositories.base import BaseRepository, serialize_row


def _json_or_none(value: Any) -> str | None:
    """列表/字典序列化为 JSON 字符串；空值返回 None。"""
    if value is None or value == [] or value == {}:
        return None
    return json.dumps(value, ensure_ascii=False)


# 分析结果中存的是 JSON 字符串、但列名**没有 _json 后缀**的字段。
# serialize_row 只按后缀反序列化，故此处显式解码，否则前端拿到字符串
# 并对它调 .map() 会抛错（曾导致详情页整体白屏）。
_JSON_FIELDS = ("domains", "evidence", "key_points")


def _decode_analysis(row: Any) -> dict[str, Any]:
    """把分析行的 JSON 字符串字段解码为结构，供前端直接消费。"""
    decoded = serialize_row(row) or {}
    for field in _JSON_FIELDS:
        value = decoded.get(field)
        if isinstance(value, str):
            try:
                decoded[field] = json.loads(value)
            except json.JSONDecodeError:
                # 非法 JSON 不应让整个详情页失败，降级为 None
                decoded[field] = None
    return decoded


class PolicyDocumentRepository(BaseRepository):
    """政策文件与分析结果仓储。"""

    def find_by_hash(self, owner_username: str, file_hash: str) -> dict[str, Any] | None:
        """按文件哈希查已上传记录（用于去重）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, title, status, created_at FROM policy_document
                        WHERE owner_username = %s AND file_hash = %s LIMIT 1""",
                    (owner_username, file_hash),
                )
                row = cursor.fetchone()
        return serialize_row(row) if row else None

    def create_document(
        self,
        owner_username: str,
        *,
        file_hash: str,
        title: str,
        original_filename: str | None,
        issuer: str | None,
        document_no: str | None,
        publish_date: Any,
        full_text: str,
        page_count: int,
    ) -> int:
        """新建政策文件记录，返回自增 id。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO policy_document
                           (owner_username, file_hash, title, original_filename, issuer,
                            document_no, publish_date, full_text, page_count, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded')""",
                    (
                        owner_username,
                        file_hash,
                        title,
                        original_filename,
                        issuer,
                        document_no,
                        publish_date,
                        full_text,
                        page_count,
                    ),
                )
                document_id = cursor.lastrowid
            conn.commit()
        return int(document_id)

    def set_status(
        self, document_id: int, status: str, error_message: str | None = None
    ) -> None:
        """更新分析状态（analyzing / completed / failed）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE policy_document
                          SET status = %s, error_message = %s,
                              updated_at = CURRENT_TIMESTAMP(6)
                        WHERE id = %s""",
                    (status, error_message, document_id),
                )
            conn.commit()

    def save_analysis(
        self, document_id: int, owner_username: str, analysis: dict[str, Any]
    ) -> None:
        """写入分析结果；同一文件重复分析时覆盖（按 document_id 唯一）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO policy_analysis
                           (document_id, owner_username, summary, domains, impact_direction,
                            impact_reason, evidence, key_points, model_name)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                           summary = VALUES(summary),
                           domains = VALUES(domains),
                           impact_direction = VALUES(impact_direction),
                           impact_reason = VALUES(impact_reason),
                           evidence = VALUES(evidence),
                           key_points = VALUES(key_points),
                           model_name = VALUES(model_name)""",
                    (
                        document_id,
                        owner_username,
                        analysis.get("summary"),
                        _json_or_none(analysis.get("domains")),
                        analysis.get("impact_direction"),
                        analysis.get("impact_reason"),
                        _json_or_none(analysis.get("evidence")),
                        _json_or_none(analysis.get("key_points")),
                        analysis.get("model_name"),
                    ),
                )
            conn.commit()

    def list_documents(
        self, owner_username: str, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        """列表（含分析状态与影响方向），按上传时间倒序。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM policy_document WHERE owner_username = %s",
                    (owner_username,),
                )
                total = int(cursor.fetchone()["total"] or 0)

                cursor.execute(
                    """SELECT d.id, d.title, d.original_filename, d.issuer, d.document_no,
                              d.publish_date, d.page_count, d.status, d.error_message,
                              d.model_name, d.created_at,
                              a.impact_direction
                         FROM policy_document d
                         LEFT JOIN policy_analysis a ON a.document_id = d.id
                        WHERE d.owner_username = %s
                        ORDER BY d.created_at DESC, d.id DESC
                        LIMIT %s OFFSET %s""",
                    (owner_username, limit, offset),
                )
                rows = cursor.fetchall()
        return {"items": [serialize_row(row) or {} for row in rows], "total": total}

    def get_document(self, owner_username: str, document_id: int) -> dict[str, Any] | None:
        """详情（含分析结果；serialize_row 会自动反序列化 *_json 列）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, title, original_filename, issuer, document_no,
                              publish_date, page_count, status, error_message,
                              model_name, created_at, full_text
                         FROM policy_document
                        WHERE id = %s AND owner_username = %s LIMIT 1""",
                    (document_id, owner_username),
                )
                document = cursor.fetchone()
                if not document:
                    return None

                cursor.execute(
                    """SELECT summary, domains, impact_direction, impact_reason,
                              evidence, key_points, model_name, created_at
                         FROM policy_analysis WHERE document_id = %s LIMIT 1""",
                    (document_id,),
                )
                analysis = cursor.fetchone()

        result = serialize_row(document) or {}
        result["analysis"] = _decode_analysis(analysis) if analysis else None
        # 正文很长，列表不返回，详情按需裁剪（前端只做预览）
        result["text_preview"] = (result.pop("full_text", "") or "")[:2000]
        return result

    def delete_document(self, owner_username: str, document_id: int) -> bool:
        """删除文件及其分析结果。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM policy_document WHERE id = %s AND owner_username = %s",
                    (document_id, owner_username),
                )
                if not cursor.fetchone():
                    return False
                cursor.execute("DELETE FROM policy_analysis WHERE document_id = %s", (document_id,))
                cursor.execute("DELETE FROM policy_document WHERE id = %s", (document_id,))
            conn.commit()
        return True