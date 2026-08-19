"""
新闻分析执行器
批量处理未分析的新闻，异步并发调用分析模块，处理结果并保存到数据库
"""

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import openai
import pymysql

# 添加在文件最开头，所有导入之前
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 全局常量：项目根路径（消除重复路径计算）
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from backend.analysis.analyzer import MODEL_NAME, analyze_bond_yield_async
from backend.analysis.result_processor import AnalysisResultProcessor
from backend.common.database import DatabaseConfig, get_db_connection, init_database
from backend.common.db_operations import DBOperations
from backend.config.config import MYSQL_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class RunStatistics:
    """运行统计信息"""

    total_news: int = 0
    processed_news: int = 0
    success_news: int = 0
    failed_news: int = 0
    skipped_news: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        """运行时长（秒）"""
        return self.end_time - self.start_time

    @property
    def processing_speed(self) -> float:
        """处理速度（条/秒）"""
        return self.processed_news / self.duration if self.duration > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_news": self.total_news,
            "processed_news": self.processed_news,
            "success_news": self.success_news,
            "failed_news": self.failed_news,
            "skipped_news": self.skipped_news,
            "duration_seconds": round(self.duration, 2),
            "processing_speed": round(self.processing_speed, 2),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
        }


class NewsAnalyzerRunner:
    """
    新闻分析执行器
    负责批量处理未分析的新闻，异步并发执行分析流程
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        model_name: str = MODEL_NAME,
    ):
        """
        初始化分析执行器
        Args:
            max_concurrent: 最大并发数
            model_name: 模型名称
        """
        self.max_concurrent = max_concurrent
        self.model_name = model_name

        # 初始化依赖组件
        self.db_ops = DBOperations()
        self.result_processor = AnalysisResultProcessor(model_name=model_name)

        # 并发控制信号量
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # 统计信息
        self.stats = RunStatistics()
        self.failed_records: List[Dict[str, Any]] = []
        self.skipped_records: List[Dict[str, Any]] = []

    async def run(
        self,
        batch_size: int = 100,
        limit: Optional[int] = None,
        mode: str = "model_missing",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        news_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        启动分析流程
        Args:
            batch_size: 每批处理的新闻数量
            limit: 最大处理数量，None表示处理所有待分析新闻
        Returns:
            统计结果字典
        """
        logger.info(
            f"启动新闻分析执行器，参数：max_concurrent={self.max_concurrent}, "
            f"batch_size={batch_size}, limit={limit}, mode={mode}, model={self.model_name}"
        )

        if mode not in ("model_missing", "force_rerun"):
            raise ValueError(f"不支持的 mode: {mode}")

        self.stats.start_time = time.time()

        try:
            while True:
                # 获取一批待分析新闻
                pending_rows = self.db_ops.get_pending_news_by_mode(
                    mode=mode,
                    model=self.model_name,
                    limit=batch_size,
                    start_time=start_time,
                    end_time=end_time,
                    news_ids=news_ids,
                )

                if not pending_rows:
                    logger.info("没有更多待分析的新闻，处理完成")
                    break

                self.stats.total_news += len(pending_rows)
                logger.info(f"获取到 {len(pending_rows)} 条待分析新闻，开始处理")

                # 并发处理这批新闻（消除冗余列表推导）
                tasks = [
                    self._process_news_with_semaphore(row["news_id"])
                    for row in pending_rows
                ]
                results = await asyncio.gather(*tasks)

                # 统计处理结果（删除死代码：异常判断）
                for result in results:
                    if result.get("status") == "success":
                        self.stats.success_news += 1
                    elif result.get("status") == "failed":
                        self.stats.failed_news += 1
                        self.failed_records.append(result)
                    elif result.get("status") == "skipped":
                        self.stats.skipped_news += 1
                        self.skipped_records.append(result)

                    self.stats.processed_news += 1

                logger.info(
                    f"批次处理完成，累计处理: {self.stats.processed_news}, "
                    f"成功: {self.stats.success_news}, 失败: {self.stats.failed_news}, 跳过: {self.stats.skipped_news}"
                )

                # 检查是否达到处理上限
                if limit is not None and self.stats.processed_news >= limit:
                    logger.info(f"已达到最大处理数量 {limit}，停止处理")
                    break

                # 短暂停顿，避免数据库压力过大
                await asyncio.sleep(1)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("收到中断信号，停止处理")
        except Exception as e:
            logger.error(f"分析流程发生严重错误: {str(e)}", exc_info=True)
            raise
        finally:
            self.stats.end_time = time.time()
            # 输出最终统计
            logger.info("=" * 60)
            logger.info("分析执行结束，统计信息:")
            logger.info(f"总新闻数: {self.stats.total_news}")
            logger.info(f"已处理: {self.stats.processed_news}")
            logger.info(f"成功: {self.stats.success_news}")
            logger.info(f"失败: {self.stats.failed_news}")
            logger.info(f"跳过: {self.stats.skipped_news}")
            logger.info(f"总耗时: {self.stats.duration:.2f} 秒")
            logger.info(f"处理速度: {self.stats.processing_speed:.2f} 条/秒")
            # 消除无用变量，直接获取报告路径
            report_file = self._write_issue_report()
            logger.info(f"失败/跳过明细已写入: {report_file}")
            logger.info("=" * 60)

        return self.stats.to_dict()

    async def _process_news_with_semaphore(self, news_id: int) -> Dict[str, Any]:
        """带信号量控制的新闻处理：重试耗尽也收敛为单条失败，避免中断整批"""
        async with self.semaphore:
            try:
                return await self._process_single_news_with_retry(news_id)
            except Exception as exc:
                logger.error(f"新闻 {news_id} 重试耗尽仍未成功: {exc}")
                return {
                    "news_id": news_id,
                    "status": "failed",
                    "reason": f"重试耗尽: {exc}",
                    "error_type": type(exc).__name__,
                    "recorded_at": datetime.now().isoformat(),
                }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (
                openai.APIError,
                openai.APIConnectionError,
                openai.RateLimitError,
                pymysql.OperationalError,
                pymysql.InterfaceError,
            )
        ),
        reraise=False,
    )
    async def _process_single_news_with_retry(self, news_id: int) -> Dict[str, Any]:
        """带重试机制的单条新闻处理"""
        return await self._process_single_news(news_id)

    async def _process_single_news(self, news_id: int) -> Dict[str, Any]:
        """处理单条新闻的完整流程"""
        logger.debug(f"开始处理新闻 {news_id}")

        # 1. 检查是否已经分析过（防并发重复入队）；DB 瞬时故障交给重试器
        try:
            if self.db_ops.get_analysis_exists(news_id, self.model_name):
                logger.info(f"新闻 {news_id} 已存在分析结果，跳过")
                return {
                    "news_id": news_id,
                    "status": "skipped",
                    "reason": "已存在分析结果",
                    "recorded_at": datetime.now().isoformat(),
                }
        except (pymysql.OperationalError, pymysql.InterfaceError) as exc:
            logger.warning(f"新闻 {news_id} 查重查询失败，交由重试器: {exc}")
            raise

        # 2. 调用分析接口；LLM 网络/限流错误交由重试器处理
        try:
            analysis_result = await analyze_bond_yield_async(
                news_id,
                model_name=self.model_name,
            )
        except (
            openai.APIError,
            openai.APIConnectionError,
            openai.RateLimitError,
        ) as exc:
            logger.warning(f"新闻 {news_id} LLM 调用失败，交由重试器: {exc}")
            raise

        try:
            # 3. 验证分析结果
            if not self.result_processor.validate_analysis_result(analysis_result):
                logger.warning(f"新闻 {news_id} 分析结果无效，使用默认结果")
                analysis_result = self._get_default_analysis_result()

            # 4. 事务性保存结果
            with get_db_connection() as conn:
                try:
                    # 保存分析主结果
                    self.db_ops.save_analysis_result(
                        news_id=news_id,
                        analysis_result=analysis_result,
                        model=self.model_name,
                        conn=conn,
                    )

                    # 处理因子并保存关联关系
                    self.result_processor.process_analysis_result(
                        news_id=news_id, analysis_result=analysis_result, conn=conn
                    )

                    conn.commit()
                    logger.info(f"新闻 {news_id} 处理成功")
                    return {
                        "news_id": news_id,
                        "status": "success",
                        "recorded_at": datetime.now().isoformat(),
                    }

                except Exception as e:
                    conn.rollback()
                    logger.error(
                        f"保存新闻 {news_id} 结果时发生错误，事务回滚: {str(e)}",
                        exc_info=True,
                    )
                    raise

        except Exception as e:
            logger.error(f"处理新闻 {news_id} 失败: {str(e)}", exc_info=True)
            return {
                "news_id": news_id,
                "status": "failed",
                "reason": str(e),
                "error_type": type(e).__name__,
                "recorded_at": datetime.now().isoformat(),
            }

    def _write_issue_report(self) -> str:
        """将本次运行的失败/跳过详情写入 JSON 文件，便于排查问题。"""
        # 复用全局常量，消除重复路径计算
        report_dir = PROJECT_ROOT / "logs" / "analysis_issues"
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = (
            report_dir
            / f"analysis_issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report = {
            "generated_at": datetime.now().isoformat(),
            "model_name": self.model_name,
            "summary": self.stats.to_dict(),
            "failed": self.failed_records,
            "skipped": self.skipped_records,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return str(report_file)

    def _get_default_analysis_result(self) -> Dict[str, Any]:
        """获取默认的分析结果（当分析失败时使用）"""
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": "分析失败，使用默认结果",
            "factors": [],
        }


async def main():
    """主函数，用于直接运行"""
    config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(config)

    parser = argparse.ArgumentParser(description="新闻分析执行器")
    parser.add_argument("--max-concurrent", type=int, default=10, help="最大并发数")
    parser.add_argument("--batch-size", type=int, default=100, help="每批处理数量")
    parser.add_argument("--limit", type=int, default=1000, help="最大处理数量")
    parser.add_argument(
        "--mode",
        type=str,
        default="model_missing",
        choices=["model_missing", "force_rerun"],
        help="执行模式",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help="起始时间，格式如 2026-05-01 00:00:00",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        help="结束时间，格式如 2026-05-09 23:59:59",
    )
    parser.add_argument(
        "--news-ids", type=str, default=None, help="新闻ID列表，逗号分隔"
    )

    args = parser.parse_args()

    runner = NewsAnalyzerRunner(
        max_concurrent=args.max_concurrent,
    )

    parsed_news_ids: Optional[List[int]] = None
    if args.news_ids:
        parsed_news_ids = [
            int(x.strip()) for x in args.news_ids.split(",") if x.strip()
        ]

    await runner.run(
        batch_size=args.batch_size,
        limit=args.limit,
        mode=args.mode,
        start_time=args.start_time,
        end_time=args.end_time,
        news_ids=parsed_news_ids,
    )


if __name__ == "__main__":
    from backend.common.logging_config import setup_logging

    setup_logging()
    asyncio.run(main())
