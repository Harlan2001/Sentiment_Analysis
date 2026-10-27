"""批量计算因子事件研究并落库。

用法：
    uv run python -m scripts.run_factor_backtest          # 全部因子
    uv run python -m scripts.run_factor_backtest 50       # 只跑事件数前 50 的因子

为什么批量落库：news_factor 有 6.4 万行，实时算会让页面请求超时；
页面只读结果（factor_event_study 表）。
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from backend.common.database import (  # noqa: E402
    DatabaseConfig,
    execute_query,
    init_database,
)
from backend.config.config import MYSQL_CONFIG  # noqa: E402
from backend.evaluation.factor_backtest import (  # noqa: E402
    HOLDING_DAYS,
    build_event_rows,
    evaluate_factor,
    trading_calendar,
)
from backend.repositories.factor_event_study_repository import (  # noqa: E402
    FactorEventStudyRepository,
)


def _load_factors(limit: int | None) -> list[tuple[str, str, int]]:
    """取因子及其事件数（按事件数降序，样本少的因子优先排除）。"""
    sql = """
        SELECT f.code, f.name, COUNT(*) AS cnt
          FROM news_factor nf
          JOIN factor f ON f.id = nf.factor_id
         WHERE f.code IS NOT NULL
         GROUP BY f.code, f.name
         ORDER BY cnt DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [(row[0], row[1] or row[0], row[2]) for row in execute_query(sql)]


def _load_events(code: str) -> list[tuple]:
    """取某因子的全部事件（时间 + 方向）。"""
    return execute_query(
        """SELECT nf.pub_time, LOWER(COALESCE(nf.direction, ''))
             FROM news_factor nf
             JOIN factor f ON f.id = nf.factor_id
            WHERE f.code = %s
            ORDER BY nf.pub_time""",
        (code,),
    )


def run(limit: int | None = None) -> dict[str, int]:
    """计算并落库，返回统计。"""
    repository = FactorEventStudyRepository.from_environment()
    calendar = trading_calendar()
    factors = _load_factors(limit)
    print(f"待计算因子: {len(factors)} 个")

    records: list[dict] = []
    for index, (code, name, count) in enumerate(factors, 1):
        events = build_event_rows(_load_events(code))
        if not events:
            continue

        # 全量口径
        for holding in HOLDING_DAYS:
            result = evaluate_factor(events, calendar, holding)
            records.append(
                {
                    "factor_code": code,
                    "factor_name": name,
                    "holding_days": holding,
                    "period_label": "all",
                    **result,
                }
            )

        # 分年度：**三个持有期都算** —— 前端的持有期切换器需要联动图表，
        # 若只算 T+5，切到 T+1/T+20 时图表不变，切换器就失去意义。
        by_year: dict[int, list] = {}
        for event in events:
            if event.pub_time is None:
                continue
            by_year.setdefault(event.pub_time.year, []).append(event)
        for year, year_events in by_year.items():
            if len(year_events) < 10:  # 年度样本过少的年份不单列
                continue
            for holding in HOLDING_DAYS:
                result = evaluate_factor(year_events, calendar, holding)
                records.append(
                    {
                        "factor_code": code,
                        "factor_name": name,
                        "holding_days": holding,
                        "period_label": str(year),
                        **result,
                    }
                )

        if index % 20 == 0:
            print(f"  已处理 {index}/{len(factors)}")

    written = repository.upsert_many(records)
    print(f"写入 {written} 条研究结果")
    return {"factors": len(factors), "records": written}


if __name__ == "__main__":
    init_database(DatabaseConfig(**MYSQL_CONFIG))
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit_arg)