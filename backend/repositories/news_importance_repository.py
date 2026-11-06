"""新闻重要性打分仓储（S3-2）。

职责：
- 批量采集打分原料（news / analysis / news_factor+factor / factor_event_study /
  news_content_blocks），组装为 recommend.importance.ImportanceInput；
- 打分结果幂等 upsert 到 news_importance_score。

纯公式在 backend.recommend.importance，本类只做 SQL 与行组装。
注意 news_factor 主键为 (news_id, factor_id, model)，因子计数必须 DISTINCT。
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Optional

from backend.common.database import build_in_placeholders
from backend.common.db_analysis import AnalysisQueries
from backend.config.config import (
    FACTOR_CATEGORY_WEIGHTS,
    RECOMMEND_DECAY_LAMBDA,
    RECOMMEND_HOLDING_DAYS,
    RECOMMEND_SCORE_VERSION,
)
from backend.recommend.importance import (
    DIRECTION_WORDS,
    FINAL_SCORE_EXPR,
    FactorStudy,
    ImportanceInput,
)
from backend.repositories.base import BaseRepository


class NewsImportanceRepository(BaseRepository):
    """news_importance_score 表与打分原料查询。"""

    # ── 打分原料采集 ─────────────────────────────────────────────────

    def fetch_signal_inputs(self, news_ids: list[int]) -> dict[int, ImportanceInput]:
        """按新闻 ID 批量采集并组装打分输入；未命中任何辅助表的新闻仍返回兜底输入。"""
        if not news_ids:
            return {}
        ids = list(dict.fromkeys(int(i) for i in news_ids))
        ph = build_in_placeholders(ids)

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT id, title, source, pub_time
                          FROM news WHERE id IN ({ph})""",
                    ids,
                )
                news_rows = cur.fetchall()

                cur.execute(
                    f"""SELECT news_id, direction, horizon, model
                          FROM analysis
                         WHERE news_id IN ({ph})
                         ORDER BY news_id, {AnalysisQueries.priority_case_sql()}""",
                    ids,
                )
                analysis_rows = cur.fetchall()

                # DISTINCT 因子：同因子多模型只算一次
                cur.execute(
                    f"""SELECT nf.news_id, nf.factor_id, f.code, f.category
                          FROM news_factor nf
                          JOIN factor f ON f.id = nf.factor_id
                         WHERE nf.news_id IN ({ph})
                         GROUP BY nf.news_id, nf.factor_id, f.code, f.category""",
                    ids,
                )
                factor_rows = cur.fetchall()

                cur.execute(
                    f"""SELECT news_id,
                               SUM(CASE WHEN block_type='image' THEN 1 ELSE 0 END) AS img_cnt,
                               SUM(CASE WHEN block_type='table' THEN 1 ELSE 0 END) AS table_cnt,
                               SUM(CASE WHEN block_type='heading' THEN 1 ELSE 0 END) AS heading_cnt
                          FROM news_content_blocks
                         WHERE news_id IN ({ph})
                         GROUP BY news_id""",
                    ids,
                )
                block_rows = {row["news_id"]: row for row in cur.fetchall()}

            # 因子回测先验：按本批因子 code 一次性取回
            factor_codes = list({row["code"] for row in factor_rows if row.get("code")})
            study_map: dict[str, dict[str, Any]] = {}
            if factor_codes:
                code_ph = build_in_placeholders(factor_codes)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT factor_code, hit_rate, majority_base, sample_size
                              FROM factor_event_study
                             WHERE period_label = 'all'
                               AND holding_days = %s
                               AND factor_code IN ({code_ph})""",
                        (RECOMMEND_HOLDING_DAYS, *factor_codes),
                    )
                    study_map = {row["factor_code"]: row for row in cur.fetchall()}

        # analysis 按新闻分组（SQL 已按模型优先级排序，首行即最佳模型）
        analysis_by_news: dict[int, list[dict]] = {}
        for row in analysis_rows:
            analysis_by_news.setdefault(row["news_id"], []).append(row)

        factors_by_news: dict[int, list[dict]] = {}
        for row in factor_rows:
            factors_by_news.setdefault(row["news_id"], []).append(row)

        inputs: dict[int, ImportanceInput] = {}
        for news in news_rows:
            news_id = news["id"]
            analyses = analysis_by_news.get(news_id, [])
            best = analyses[0] if analyses else {}
            factors = factors_by_news.get(news_id, [])

            categories = list({(f.get("category") or "").upper() for f in factors if f.get("category")})
            # 每个 DISTINCT 因子一个先验；缺回测行的因子交给 hit_prior 兜底为 0.5
            studies: list[FactorStudy] = []
            for factor in factors:
                code = factor.get("code")
                study = study_map.get(code) if code else None
                studies.append(
                    FactorStudy(
                        factor_code=code or "",
                        hit_rate=study.get("hit_rate") if study else None,
                        majority_base=study.get("majority_base") if study else None,
                        sample_size=int(study["sample_size"]) if study and study.get("sample_size") is not None else 0,
                    )
                )

            blocks = block_rows.get(news_id, {})
            inputs[news_id] = ImportanceInput(
                news_id=news_id,
                title=news.get("title") or "",
                source=news.get("source"),
                best_direction=best.get("direction"),
                all_directions=[row.get("direction") for row in analyses],
                horizon=best.get("horizon"),
                factor_categories=categories,
                factor_studies=studies,
                factor_count=len(factors),
                has_image=int(blocks.get("img_cnt") or 0) > 0,
                has_table=int(blocks.get("table_cnt") or 0) > 0,
                heading_count=int(blocks.get("heading_cnt") or 0),
            )
        return inputs

    def iter_news_ids(
        self,
        window_days: Optional[int] = None,
        batch_size: int = 500,
    ) -> Iterator[list[int]]:
        """分批产出新闻 ID。window_days 给定时只取近 N 天，否则全量。"""
        with self._connection() as conn:
            with conn.cursor() as cur:
                where = ""
                params: tuple = ()
                if window_days:
                    where = "WHERE pub_time >= DATE_SUB(NOW(), INTERVAL %s DAY)"
                    params = (int(window_days),)
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM news {where}",
                    params,
                )
                total = int(cur.fetchone()["cnt"])

                offset = 0
                while offset < total:
                    cur.execute(
                        f"""SELECT id FROM news {where}
                             ORDER BY id LIMIT %s OFFSET %s""",
                        (*params, batch_size, offset),
                    )
                    yield [row["id"] for row in cur.fetchall()]
                    offset += batch_size

    # ── 结果写入 ─────────────────────────────────────────────────────

    def upsert_many(self, results: list, version: str = RECOMMEND_SCORE_VERSION) -> int:
        """批量幂等写入打分结果（按 news_id + score_version），返回写入条数。"""
        if not results:
            return 0
        fields = (
            "news_id", "score_version", "importance_score", "s_direction", "s_agreement",
            "s_horizon", "s_category", "s_hit", "s_nfactor", "s_rich", "s_policy",
            "s_source", "factor_count", "top_category", "signals_json",
        )
        columns = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        updates = ", ".join(
            f"{field} = VALUES({field})"
            for field in fields
            if field not in {"news_id", "score_version"}
        )
        sql = (
            f"INSERT INTO news_importance_score ({columns}) VALUES ({placeholders})"
            f" ON DUPLICATE KEY UPDATE {updates}"
        )

        rows = []
        for result in results:
            signals = result.signals
            rows.append((
                result.news_id,
                version,
                result.score,
                signals["s_direction"],
                signals["s_agreement"],
                signals["s_horizon"],
                signals["s_category"],
                signals["s_hit"],
                signals["s_nfactor"],
                signals["s_rich"],
                int(signals["s_policy"]),
                signals["s_source"],
                result.factor_count,
                result.top_category,
                json.dumps(signals, ensure_ascii=False),
            ))

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()
        return len(rows)

    def get_by_news_ids(
        self,
        news_ids: list[int],
        version: str = RECOMMEND_SCORE_VERSION,
    ) -> dict[int, dict[str, Any]]:
        """读取已落表的打分结果（脚本/测试校验用）。"""
        if not news_ids:
            return {}
        ph = build_in_placeholders(news_ids)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT * FROM news_importance_score
                         WHERE score_version = %s AND news_id IN ({ph})""",
                    (version, *news_ids),
                )
                return {row["news_id"]: row for row in cur.fetchall()}

    # ── 排行榜（S3-3）────────────────────────────────────────────────

    def _window_clause(self, days: int) -> tuple[str, tuple]:
        return "n.pub_time >= DATE_SUB(NOW(), INTERVAL %s DAY)", (int(days),)

    def top_news(
        self,
        days: int,
        limit: int = 10,
        direction: Optional[str] = None,
        version: str = RECOMMEND_SCORE_VERSION,
    ) -> list[dict[str, Any]]:
        """窗口内按 final_score（静态分×读时衰减）排序的新闻榜。

        direction 给 positive/negative 时追加最佳模型方向归一化过滤（多空榜复用）；
        只 INNER JOIN 已打分新闻，排行榜不展示未打分条目。
        """
        where, params = self._window_clause(days)
        join_sql = AnalysisQueries.best_analysis_join()
        if direction in DIRECTION_WORDS:
            words = DIRECTION_WORDS[direction]
            where += f" AND LOWER(a.direction) IN ({build_in_placeholders(words)})"
            params += words
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT n.id, n.title, n.pub_time, n.source,
                               s.importance_score,
                               {FINAL_SCORE_EXPR} AS final_score,
                               a.direction AS best_direction, s.top_category
                          FROM news n
                          JOIN news_importance_score s
                            ON s.news_id = n.id AND s.score_version = %s
                          {join_sql}
                         WHERE {where}
                         ORDER BY final_score DESC, n.pub_time DESC, n.id DESC
                         LIMIT %s""",
                    (-RECOMMEND_DECAY_LAMBDA, version, *params, int(limit)),
                )
                return list(cur.fetchall())

    def hot_factors(self, days: int, limit: int = 10) -> list[dict[str, Any]]:
        """窗口内按 DISTINCT 关联新闻数排名的因子榜，附事件研究 hit_rate。"""
        where, params = self._window_clause(days)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT f.id, f.name, f.category,
                               COUNT(DISTINCT nf.news_id) AS news_count,
                               es.hit_rate
                          FROM news_factor nf
                          JOIN factor f ON f.id = nf.factor_id
                          JOIN news n ON n.id = nf.news_id
                          LEFT JOIN factor_event_study es
                            ON es.factor_code = f.code
                           AND es.period_label = 'all'
                           AND es.holding_days = %s
                         WHERE {where}
                         GROUP BY f.id, f.name, f.category, es.hit_rate
                         ORDER BY news_count DESC, f.id
                         LIMIT %s""",
                    (RECOMMEND_HOLDING_DAYS, *params, int(limit)),
                )
                return list(cur.fetchall())

    def category_distribution(self, days: int) -> list[dict[str, Any]]:
        """六类因子在窗口内的关联新闻数与占比（占比在 Python 侧归一）。"""
        categories = tuple(FACTOR_CATEGORY_WEIGHTS.keys())
        where, params = self._window_clause(days)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT UPPER(f.category) AS category,
                               COUNT(DISTINCT nf.news_id) AS news_count
                          FROM news_factor nf
                          JOIN factor f ON f.id = nf.factor_id
                          JOIN news n ON n.id = nf.news_id
                         WHERE {where}
                           AND UPPER(f.category) IN ({build_in_placeholders(categories)})
                         GROUP BY UPPER(f.category)""",
                    (*params, *categories),
                )
                rows = list(cur.fetchall())
        total = sum(int(r["news_count"] or 0) for r in rows)
        result = []
        for row in rows:
            count = int(row["news_count"] or 0)
            result.append({
                "category": row["category"],
                "news_count": count,
                "share": round(count / total, 4) if total else 0.0,
            })
        result.sort(key=lambda item: item["news_count"], reverse=True)
        return result
