"""因子事件研究结果的仓储。

写入由批量脚本产出的事件研究结果，供因子详情页读取。
"""

from __future__ import annotations

from typing import Any

from backend.repositories.base import BaseRepository, serialize_row


class FactorEventStudyRepository(BaseRepository):
    """因子事件研究结果仓储。"""

    def upsert_many(self, records: list[dict[str, Any]]) -> int:
        """批量写入研究结果（按 因子+持有期+分组 幂等），返回写入条数。"""
        if not records:
            return 0

        fields = (
            "factor_code", "factor_name", "holding_days", "sample_size", "hit_count",
            "hit_rate", "majority_base", "avg_move_bp", "median_move_bp",
            "period_start", "period_end", "period_label",
        )
        columns = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        updates = ", ".join(
            f"{field} = VALUES({field})"
            for field in fields
            if field not in {"factor_code", "holding_days", "period_label"}
        )

        with self._connection() as conn:
            with conn.cursor() as cursor:
                for record in records:
                    cursor.execute(
                        f"""INSERT INTO factor_event_study ({columns}, computed_at)
                            VALUES ({placeholders}, NOW())
                            ON DUPLICATE KEY UPDATE {updates}, computed_at = NOW()""",
                        tuple(record.get(field) for field in fields),
                    )
            conn.commit()
        return len(records)

    def get_factor_performance(self, factor_code: str) -> dict[str, Any]:
        """某因子的历史表现：各持有期汇总 + 分年度表现（含各持有期）。

        返回 {holding: [...], yearly: [...], computed_at}。
        分年度带 holding_days，供前端按当前持有期筛选，实现切换联动。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT holding_days, sample_size, hit_count, hit_rate,
                              majority_base, avg_move_bp, median_move_bp,
                              period_start, period_end, computed_at
                         FROM factor_event_study
                        WHERE factor_code = %s AND period_label = 'all'
                        ORDER BY holding_days""",
                    (factor_code,),
                )
                holding = [serialize_row(row) or {} for row in cursor.fetchall()]

                cursor.execute(
                    """SELECT period_label, holding_days, sample_size, hit_rate,
                              majority_base, avg_move_bp
                         FROM factor_event_study
                        WHERE factor_code = %s AND period_label <> 'all'
                        ORDER BY holding_days, period_label""",
                    (factor_code,),
                )
                yearly = [serialize_row(row) or {} for row in cursor.fetchall()]

        computed_at = holding[0].get("computed_at") if holding else None
        return {"factor_code": factor_code, "holding": holding, "yearly": yearly,
                "computed_at": computed_at, "min_samples": 20}

    def list_overview(self, holding_days: int = 5, min_samples: int = 20) -> dict[str, Any]:
        """回测仿真总览：各因子的历史表现列表 + 整体分布。

        用途：回测仿真页需要一屏看多个因子，并给出整体分布统计。
        与因子详情页的单因子视角互补，不替代。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT s.factor_code, s.factor_name, s.sample_size, s.hit_rate,
                              s.majority_base, s.avg_move_bp, s.median_move_bp,
                              f.id AS factor_id
                         FROM factor_event_study s
                         LEFT JOIN factor f ON f.code = s.factor_code
                        WHERE s.period_label = 'all' AND s.holding_days = %s
                        ORDER BY s.sample_size DESC""",
                    (holding_days,),
                )
                rows = [serialize_row(row) or {} for row in cursor.fetchall()]

                # 整体分布：用于页面顶部的统计概览
                cursor.execute(
                    """SELECT COUNT(*) AS factors,
                              SUM(sample_size) AS total_samples,
                              AVG(hit_rate) AS avg_hit_rate,
                              AVG(majority_base) AS avg_base,
                              SUM(CASE WHEN sample_size >= %s THEN 1 ELSE 0 END) AS sufficient,
                              SUM(CASE WHEN sample_size >= %s AND hit_rate > majority_base
                                       THEN 1 ELSE 0 END) AS above_base
                         FROM factor_event_study
                        WHERE period_label = 'all' AND holding_days = %s""",
                    (min_samples, min_samples, holding_days),
                )
                summary_row = serialize_row(cursor.fetchone()) or {}

        items = []
        for row in rows:
            sample = int(row.get("sample_size") or 0)
            hit = row.get("hit_rate")
            base = row.get("majority_base")
            items.append(
                {
                    **row,
                    "sufficient": sample >= min_samples,
                    # 命中率与基准之差（pt），便于一眼看出偏离方向
                    "delta": (
                        round(float(hit) - float(base), 4)
                        if hit is not None and base is not None
                        else None
                    ),
                }
            )

        return {
            "holding_days": holding_days,
            "min_samples": min_samples,
            "summary": {
                "factors": int(summary_row.get("factors") or 0),
                "total_samples": int(summary_row.get("total_samples") or 0),
                "avg_hit_rate": (
                    round(float(summary_row["avg_hit_rate"]), 4)
                    if summary_row.get("avg_hit_rate") is not None
                    else None
                ),
                "avg_base": (
                    round(float(summary_row["avg_base"]), 4)
                    if summary_row.get("avg_base") is not None
                    else None
                ),
                "sufficient": int(summary_row.get("sufficient") or 0),
                "above_base": int(summary_row.get("above_base") or 0),
            },
            "items": items,
        }
