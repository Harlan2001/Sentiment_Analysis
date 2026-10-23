"""一次性回填：抓取近 N 个交易日的国债期货持仓并入库。

用途：趋势图需要历史才有意义。属一次性工具脚本，非定时任务。
用法：uv run python -m scripts.backfill_futures_position 60
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

from backend.common.database import DatabaseConfig, init_database  # noqa: E402
from backend.config.config import MYSQL_CONFIG  # noqa: E402
from backend.repositories.futures_position_repository import (  # noqa: E402
    FuturesPositionRepository,
)
from backend.tools.futures_source import FuturesSourceError, fetch_positions  # noqa: E402


def backfill(days: int = 60) -> dict[str, int]:
    """从今天往前逐自然日尝试抓取（非交易日无文件则跳过）。"""
    repository = FuturesPositionRepository.from_environment()
    today = date.today()
    fetched_days = 0
    total_records = 0
    inserted = updated = 0

    for offset in range(days):
        target = today - timedelta(days=offset)
        if target.weekday() >= 5:  # 周末直接跳过，减少无效请求
            continue
        try:
            records = fetch_positions(target)
        except FuturesSourceError:
            continue  # 节假日/无数据，正常跳过
        stats = repository.upsert_many(records)
        fetched_days += 1
        total_records += len(records)
        inserted += stats["inserted"]
        updated += stats["updated"]
        print(f"  {target} 抓取 {len(records)} 条（新增 {stats['inserted']} / 更新 {stats['updated']}）")

    return {
        "fetched_days": fetched_days,
        "total_records": total_records,
        "inserted": inserted,
        "updated": updated,
    }


if __name__ == "__main__":
    init_database(DatabaseConfig(**MYSQL_CONFIG))
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    print(f"开始回填近 {days} 天…")
    result = backfill(days)
    print(f"完成：{result['fetched_days']} 个交易日，{result['total_records']} 条记录")
    print(f"  新增 {result['inserted']} / 更新 {result['updated']}")