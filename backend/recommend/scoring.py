"""打分编排（S3-2）：采集原料 → 纯函数计算 → 幂等落库。

被两处复用：
- scripts/recompute_news_importance.py：全量/窗口回算；
- analyzer_runner：单新闻分析事务提交后的增量打分。
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.config.config import RECOMMEND_SCORE_VERSION
from backend.recommend.importance import ImportanceInput, compute_static_score
from backend.repositories.news_importance_repository import NewsImportanceRepository

logger = logging.getLogger(__name__)


def score_news_ids(
    news_ids: list[int],
    *,
    version: str = RECOMMEND_SCORE_VERSION,
    repository: Optional[NewsImportanceRepository] = None,
) -> int:
    """对给定新闻打分并 upsert，返回写入条数。空输入直接返回 0。"""
    if not news_ids:
        return 0
    repo = repository or NewsImportanceRepository.from_environment()
    inputs: dict[int, ImportanceInput] = repo.fetch_signal_inputs(list(news_ids))
    results = [compute_static_score(inp) for inp in inputs.values()]
    written = repo.upsert_many(results, version=version)
    logger.info("新闻重要性打分完成: 请求 %d 条, 写入 %d 条 (version=%s)",
                len(news_ids), written, version)
    return written


def score_all(
    *,
    window_days: Optional[int] = None,
    batch_size: int = 500,
    version: str = RECOMMEND_SCORE_VERSION,
) -> int:
    """全量或近 N 天窗口分批回算，返回累计写入条数。"""
    repo = NewsImportanceRepository.from_environment()
    total = 0
    for batch in repo.iter_news_ids(window_days=window_days, batch_size=batch_size):
        total += score_news_ids(batch, version=version, repository=repo)
    logger.info("新闻重要性回算结束: 累计写入 %d 条 (window_days=%s)", total, window_days)
    return total
