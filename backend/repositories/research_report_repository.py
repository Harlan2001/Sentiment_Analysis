"""research_report 表数据访问：研报列表 + 机构/行业筛选面。

研报浏览器（routers/research.py /list）与研报生成来源选择
（ReportGenerationRepository.list_sources）共用本仓储，消除两处重复 SQL。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.repositories.base import BaseRepository, RepositoryError


class ResearchReportConflictError(RepositoryError):
    """研报当前状态不允许执行该操作。"""

    status_code = 409


class ResearchReportRepository(BaseRepository):
    """研报列表 / 筛选面查询。"""

    def _build_where(
        self,
        *,
        keyword: str | None = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: str | None = None,
        industry: str | None = None,
        market_view: str | None = None,
        status: str | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> tuple[str, list[Any]]:
        """根据筛选条件生成 WHERE 子句与参数。"""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if keyword:
            cols = " OR ".join(f"{col} LIKE %s" for col in keyword_columns)
            conditions.append(f"({cols})")
            params.extend([f"%{keyword}%"] * len(keyword_columns))
        if institution:
            conditions.append("institution = %s")
            params.append(institution)
        if industry:
            conditions.append("industry LIKE %s")
            params.append(f"%{industry}%")
        if market_view:
            conditions.append("ai_market_view = %s")
            params.append(market_view)
        if date_start:
            conditions.append("publish_date >= %s")
            params.append(date_start)
        if date_end:
            conditions.append("publish_date <= %s")
            params.append(date_end)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params

    def query_reports(
        self,
        *,
        columns: tuple[str, ...],
        keyword: str | None = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: str | None = None,
        industry: str | None = None,
        market_view: str | None = None,
        status: str | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
        limit: int | None = None,
        offset: int = 0,
        order_by: str = "publish_date DESC, id DESC",
    ) -> list[dict[str, Any]]:
        """按筛选条件查询研报（返回 DictCursor 原始字典行）。"""
        where, params = self._build_where(
            keyword=keyword,
            keyword_columns=keyword_columns,
            institution=institution,
            industry=industry,
            market_view=market_view,
            status=status,
            date_start=date_start,
            date_end=date_end,
        )
        cols = ", ".join(columns)
        sql = f"SELECT {cols} FROM research_report {where} ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
            if offset:
                sql += " OFFSET %s"
                params.append(offset)

        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return list(cursor.fetchall())

    def count_reports(
        self,
        *,
        keyword: str | None = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: str | None = None,
        industry: str | None = None,
        market_view: str | None = None,
        status: str | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> int:
        """统计符合筛选条件的研报数量。"""
        where, params = self._build_where(
            keyword=keyword,
            keyword_columns=keyword_columns,
            institution=institution,
            industry=industry,
            market_view=market_view,
            status=status,
            date_start=date_start,
            date_end=date_end,
        )
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM research_report {where}",
                    tuple(params),
                )
                row = cursor.fetchone()
        return int(row["total"]) if row else 0

    def get_filter_facets(
        self, *, status: str | None = None
    ) -> dict[str, list[str]]:
        """机构/行业筛选面（可选 status 约束，默认不约束）。"""
        status_cond = "AND status = %s" if status else ""
        status_param: tuple[Any, ...] = (status,) if status else ()

        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT DISTINCT institution FROM research_report
                        WHERE institution IS NOT NULL AND institution <> '' {status_cond}
                        ORDER BY institution""",
                    status_param,
                )
                institutions = [row["institution"] for row in cursor.fetchall()]
                cursor.execute(
                    f"""SELECT DISTINCT industry FROM research_report
                        WHERE industry IS NOT NULL AND industry <> '' {status_cond}"""
                )
                industries: set[str] = set()
                for row in cursor.fetchall():
                    industries.update(
                        item.strip()
                        for item in row["industry"].split(",")
                        if item.strip()
                    )

        return {"institutions": institutions, "industries": sorted(industries)}

    # ========================================================================
    # 入库与分析链路（service 层不再内联 SQL）
    # ========================================================================

    def find_by_hash(self, file_hash: str) -> dict[str, Any] | None:
        """按文件哈希查重：命中返回已有行（id/title/status），未命中返回 None。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, title, status FROM research_report WHERE file_hash=%s",
                    (file_hash,),
                )
                row = cursor.fetchone()
        return row

    def ingest_report(
        self, report: dict[str, Any], figures: list[dict[str, Any]]
    ) -> int:
        """单事务内写入研报 + 图表，返回新研报 id。

        ``report`` 为已格式化好的列值（分隔符拼接、截断等由调用方处理）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_report
                    (title, institution, analyst, publish_date, industry, symbols, report_type,
                     file_path, file_hash, file_size_kb, page_count,
                     full_text, status, source, uploaded_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'parsed', %s, %s)
                    """,
                    (
                        report["title"],
                        report["institution"],
                        report["analyst"],
                        report["publish_date"],
                        report["industry"],
                        report["symbols"],
                        report["report_type"],
                        report["rel_path"],
                        report["file_hash"],
                        report["file_size_kb"],
                        report["page_count"],
                        report["full_text"],
                        report["source"],
                        report["uploaded_by"],
                    ),
                )
                report_id = cursor.lastrowid

                for fig in figures:
                    cursor.execute(
                        """
                        INSERT INTO report_figure
                        (report_id, page_number, figure_order, figure_type, caption,
                         image_path, image_size_kb)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            report_id,
                            fig["page_number"],
                            fig["figure_order"],
                            fig.get("figure_type"),
                            fig.get("caption"),
                            fig["image_path"],
                            fig["image_size_kb"],
                        ),
                    )
            conn.commit()
        return report_id

    def claim_for_analysis(self, report_id: int) -> bool:
        """抢占分析任务：仅 status IN ('parsed','failed') 可转为 processing。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE research_report SET status='processing'
                    WHERE id=%s AND status IN ('parsed','failed')
                    """,
                    (report_id,),
                )
                claimed = cursor.rowcount == 1
            conn.commit()
        return claimed

    def reset_for_reanalysis(self, report_id: int) -> None:
        """把已分析（analyzed）研报重置为 parsed，使其可被 claim_for_analysis 抢占。

        仅 analyzed 可重置；parsed/processing/failed 走原有触发流程或直接重试，
        非 analyzed 重置视为冲突。已有 ai_* 结果保留，直到新分析成功才覆盖
        （失败不得覆盖旧结果）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE research_report SET status='parsed' WHERE id=%s AND status='analyzed'",
                    (report_id,),
                )
                reset = cursor.rowcount == 1
            conn.commit()
        if not reset:
            raise ResearchReportConflictError(
                f"研报 {report_id} 当前状态不允许重新分析（仅已分析的研报可重置）"
            )

    def get_analysis_input(
        self, report_id: int, *, figure_limit: int
    ) -> tuple[str, str, list[str]] | None:
        """读取分析所需数据：标题、全文、有效图表 image_path 列表。

        图表按大小倒序取前 ``figure_limit`` 张（image_size_kb > 15 过滤装饰图）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT title, full_text FROM research_report WHERE id=%s",
                    (report_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                cursor.execute(
                    """
                    SELECT image_path FROM report_figure
                    WHERE report_id=%s AND image_size_kb > 15
                    ORDER BY image_size_kb DESC LIMIT %s
                    """,
                    (report_id, figure_limit),
                )
                image_paths = [r["image_path"] for r in cursor.fetchall()]
        return row["title"], row["full_text"], image_paths

    def finish_analysis(
        self,
        report_id: int,
        *,
        model_name: str,
        parsed: dict[str, Any],
        raw: str,
        deep_markdown: str | None = None,
    ) -> None:
        """写入 AI 分析结果，状态转 analyzed。

        ``deep_markdown`` 为板块一深度拆解全文，写入 ai_deep_markdown；
        仅在新分析成功时随本事务一起覆盖旧结果。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE research_report SET
                        ai_summary=%s, ai_key_points=%s, ai_symbols=%s, ai_industries=%s,
                        ai_market_view=%s, ai_view_strength=%s, ai_time_horizon=%s,
                        ai_evidence=%s, ai_deep_markdown=%s,
                        ai_analyzed_at=NOW(), ai_model=%s, ai_raw_response=%s,
                        status='analyzed', parse_error=NULL
                    WHERE id=%s
                    """,
                    (
                        str(parsed.get("summary", ""))[:1024],
                        json.dumps(parsed.get("key_points", []), ensure_ascii=False),
                        json.dumps(parsed.get("symbols", []), ensure_ascii=False),
                        json.dumps(parsed.get("industries", []), ensure_ascii=False),
                        parsed.get("market_view", "neutral"),
                        float(parsed.get("view_strength", 0.5) or 0.5),
                        parsed.get("time_horizon", "medium"),
                        json.dumps(parsed.get("evidence", []), ensure_ascii=False),
                        deep_markdown,
                        model_name,
                        json.dumps(raw, ensure_ascii=False)
                        if isinstance(raw, str)
                        else raw,
                        report_id,
                    ),
                )
            conn.commit()

    def mark_analysis_failed(self, report_id: int, error_message: str) -> None:
        """分析失败：状态转 failed，重试次数 +1。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE research_report SET
                        status='failed', parse_error=%s,
                        retry_count=COALESCE(retry_count,0)+1
                    WHERE id=%s
                    """,
                    (error_message[:500], report_id),
                )
            conn.commit()