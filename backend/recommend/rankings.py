"""推荐排行榜编排（S3-3）。

repository 只出 SQL 行，本模块负责：
- 行 → API 载荷的塑形与类型收窄（Decimal/float、日期格式化）；
- 数据源名称合规脱敏（NEWS_SOURCE_LABELS，不向前端暴露真实来源名）；
- 方向词归一化（与打分共用 recommend.importance.normalize_direction）。

四榜一次返回：新闻榜 / 热门因子 / 多空榜（利多利空各 Top5）/ 因子类别分布。
路由层负责 TTL 缓存与参数校验，本模块保持无 HTTP 依赖、可单测。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from backend.config.config import NEWS_SOURCE_LABELS
from backend.recommend.importance import normalize_direction
from backend.repositories.news_importance_repository import NewsImportanceRepository

_TOP_NEWS_LIMIT = 10
_DIRECTION_BOARD_LIMIT = 5
_HOT_FACTOR_LIMIT = 10


def _fmt_pub_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 4)


def _shape_news_row(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("source")
    return {
        "id": int(row["id"]),
        "title": row.get("title") or "",
        "pub_time": _fmt_pub_time(row.get("pub_time")),
        "source_name": NEWS_SOURCE_LABELS.get(source, source or ""),
        "direction": normalize_direction(row.get("best_direction")),
        "importance_score": _to_float(row.get("importance_score")),
        "final_score": _to_float(row.get("final_score")),
        "top_category": row.get("top_category"),
    }


def _shape_factor_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row.get("name") or "",
        "category": row.get("category") or "",
        "news_count": int(row.get("news_count") or 0),
        "hit_rate": _to_float(row.get("hit_rate")),
    }


def build_rankings(
    days: int,
    repository: Optional[NewsImportanceRepository] = None,
) -> dict[str, Any]:
    """聚合四榜。repository 可注入便于单测；默认走环境连接池。"""
    repo = repository or NewsImportanceRepository.from_environment()

    top_news = [_shape_news_row(row) for row in repo.top_news(days, limit=_TOP_NEWS_LIMIT)]
    hot_factors = [_shape_factor_row(row) for row in repo.hot_factors(days, limit=_HOT_FACTOR_LIMIT)]
    positive_board = [
        _shape_news_row(row)
        for row in repo.top_news(days, limit=_DIRECTION_BOARD_LIMIT, direction="positive")
    ]
    negative_board = [
        _shape_news_row(row)
        for row in repo.top_news(days, limit=_DIRECTION_BOARD_LIMIT, direction="negative")
    ]

    return {
        "days": int(days),
        "top_news": top_news,
        "hot_factors": hot_factors,
        "direction_board": {
            "positive": positive_board,
            "negative": negative_board,
        },
        "category_distribution": repo.category_distribution(days),
    }
