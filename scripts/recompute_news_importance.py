"""批量（重新）计算新闻重要性静态分并落库（S3-2）。

用法：
    uv run python -m scripts.recompute_news_importance --all              # 全量回算
    uv run python -m scripts.recompute_news_importance --window 30        # 仅近 30 天
    uv run python -m scripts.recompute_news_importance --all --version v1 # 指定公式版本

为什么预计算：静态分量在新闻分析完成后基本不再变化，实时聚合 news_factor /
news_content_blocks / 多模型 analysis 会让分页接口承担多 JOIN + filesort 成本；
时间衰减一项留待查询时用 SQL EXP() 实时施加。
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from backend.common.database import DatabaseConfig, init_database  # noqa: E402
from backend.config.config import MYSQL_CONFIG, RECOMMEND_SCORE_VERSION  # noqa: E402
from backend.recommend.scoring import score_all  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="新闻重要性分回算")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="全量回算所有新闻")
    scope.add_argument("--window", type=int, metavar="N", help="仅回算近 N 天新闻")
    parser.add_argument("--version", default=RECOMMEND_SCORE_VERSION, help="打分公式版本")
    parser.add_argument("--batch-size", type=int, default=500, help="分批大小")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_database(DatabaseConfig(**MYSQL_CONFIG))

    started = time.time()
    written = score_all(
        window_days=None if args.all else args.window,
        batch_size=args.batch_size,
        version=args.version,
    )
    elapsed = time.time() - started
    scope = "全量" if args.all else f"近 {args.window} 天"
    print(f"[{scope}] 新闻重要性回算完成: 写入 {written} 条, 耗时 {elapsed:.1f}s, version={args.version}")


if __name__ == "__main__":
    main()
