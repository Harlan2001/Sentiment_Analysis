"""非结构化因子原始事件流的只读仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.common.database import build_in_placeholders
from backend.common.pagination import offset
from backend.repositories.base import BaseRepository, serialize_row


class FactorEventRepository(BaseRepository):
    """按单一模型和新闻发布时间读取因子事件，供外部回测拉取。"""

    def list_events(
        self,
        *,
        factor_codes: list[str],
        start_time: datetime,
        end_time: datetime,
        model: str,
        include_neutral: bool,
        direction: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """返回稳定时间升序的事件页与相同过滤条件下的总数。"""
        direction_sql = "LOWER(COALESCE(nf.direction, 'neutral'))"
        where = ["nf.model = %s", "nf.pub_time >= %s", "nf.pub_time <= %s"]
        params: list[Any] = [model, start_time, end_time]

        if factor_codes:
            placeholders = build_in_placeholders(factor_codes)
            where.append(f"f.code IN ({placeholders})")
            params.extend(factor_codes)

        if direction is not None:
            where.append(f"{direction_sql} = %s")
            params.append(direction)
        elif include_neutral:
            where.append(f"{direction_sql} IN ('positive', 'negative', 'neutral')")
        else:
            where.append(f"{direction_sql} IN ('positive', 'negative')")

        where_sql = " AND ".join(where)
        from_sql = f"""FROM news_factor nf
                       JOIN factor f ON f.id = nf.factor_id
                       JOIN news n ON n.id = nf.news_id
                       WHERE {where_sql}"""

        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS total {from_sql}", tuple(params))
                count_row = cursor.fetchone() or {}
                total = int(count_row.get("total") or 0)

                cursor.execute(
                    f"""SELECT nf.pub_time, nf.news_id,
                               f.code AS factor_code, f.category, f.factor_type,
                               {direction_sql} AS direction, nf.model,
                               n.title, nf.driver
                          {from_sql}
                         ORDER BY nf.pub_time ASC, nf.news_id ASC, nf.factor_id ASC
                         LIMIT %s OFFSET %s""",
                    (*params, page_size, offset(page, page_size)),
                )
                items = [serialize_row(row) or {} for row in cursor.fetchall()]

        return {"items": items, "total": total}
