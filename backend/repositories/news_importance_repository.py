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
    RECOMMEND_HOLDING_DAYS,
    RECOMMEND_SCORE_VERSION,
)
from backend.recommend.importance import FactorStudy, ImportanceInput
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
