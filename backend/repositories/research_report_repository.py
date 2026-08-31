"""research_report 表数据访问：研报列表 + 机构/行业筛选面。

研报浏览器（routers/research.py /list）与研报生成来源选择
（ReportGenerationRepository.list_sources）共用本仓储，消除两处重复 SQL。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator, Optional

import pymysql
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG


class ResearchReportRepository:
    """研报列表 / 筛选面查询。"""

    def __init__(self, settings: dict[str, Any]):
        self._settings = settings

    @classmethod
    def from_environment(cls) -> "ResearchReportRepository":
        return cls(dict(MYSQL_CONFIG))

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

    def _build_where(
        self,
        *,
        keyword: Optional[str] = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: Optional[str] = None,
        industry: Optional[str] = None,
        market_view: Optional[str] = None,
        status: Optional[str] = None,
        date_start: Optional[date] = None,
        date_end: Optional[date] = None,
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
        keyword: Optional[str] = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: Optional[str] = None,
        industry: Optional[str] = None,
        market_view: Optional[str] = None,
        status: Optional[str] = None,
        date_start: Optional[date] = None,
        date_end: Optional[date] = None,
        limit: Optional[int] = None,
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
        keyword: Optional[str] = None,
        keyword_columns: tuple[str, ...] = ("title", "ai_summary"),
        institution: Optional[str] = None,
        industry: Optional[str] = None,
        market_view: Optional[str] = None,
        status: Optional[str] = None,
        date_start: Optional[date] = None,
        date_end: Optional[date] = None,
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
        self, *, status: Optional[str] = None
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