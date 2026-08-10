"""
集中式日志配置模块。

提供统一的日志管理，所有日志同时输出到控制台和文件（按天轮转）。
Windows 多进程环境下 TimedRotatingFileHandler 重命名冲突 → 使用 SafeRotatingFileHandler 自动容错。

导出：
- setup_logging()          — 幂等地应用日志配置（dictConfig）
- get_uvicorn_log_config() — 返回 dictConfig 字典，供 uvicorn.run(log_config=...) 使用
- add_logger_daily_file()  — 为指定 logger 附加独立的按天轮转日志文件

默认值从 backend.config.config 的环境变量读取：
- LOG_LEVEL:    日志级别，默认 INFO
- LOG_DIR:      日志目录，默认项目根目录下的 logs/
- LOG_MAX_DAYS: 日志保留天数，默认 30
"""

from __future__ import annotations

import logging
import logging.config
import logging.handlers
import os
from pathlib import Path
from typing import Optional

_initialized = False

STANDARD_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
STANDARD_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class SafeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Windows 多进程安全的轮转日志处理器。
    当日志文件被其他进程占用导致重命名失败时，不抛异常、不中断请求。
    """

    def doRollover(self):
        if not os.path.exists(self.baseFilename):
            # 文件已被其他进程重命名，直接重建
            self.stream = self._open()
            return
        try:
            super().doRollover()
        except PermissionError:
            # Windows 多进程文件锁冲突 → 跳过本次轮转，不中断业务
            self.stream = self._open()


def _resolve_defaults(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    log_max_days: Optional[int] = None,
) -> tuple[str, str, int]:
    from backend.config.config import LOG_DIR, LOG_LEVEL, LOG_MAX_DAYS  # noqa: E402

    return (
        log_dir or LOG_DIR,
        log_level or LOG_LEVEL,
        log_max_days if log_max_days is not None else LOG_MAX_DAYS,
    )


def _build_log_config(log_dir: str, log_level: str, log_max_days: int) -> dict:
    """构建 dictConfig 兼容的配置字典。"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": STANDARD_FORMAT,
                "datefmt": STANDARD_DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stderr",
            },
            "app_file": {
                "class": "backend.common.logging_config.SafeRotatingFileHandler",
                "level": log_level,
                "formatter": "standard",
                "filename": str(log_path / "app.log"),
                "when": "midnight",
                "interval": 1,
                "backupCount": log_max_days,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "backend.common.logging_config.SafeRotatingFileHandler",
                "level": "ERROR",
                "formatter": "standard",
                "filename": str(log_path / "error.log"),
                "when": "midnight",
                "interval": 1,
                "backupCount": log_max_days,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # root logger — 所有模块的 getLogger(__name__) 自动继承
                "handlers": ["console", "app_file", "error_file"],
                "level": log_level,
                "propagate": True,
            },
            "uvicorn": {
                "handlers": ["console", "app_file", "error_file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "app_file", "error_file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console", "app_file", "error_file"],
                "level": log_level,
                "propagate": False,
            },
            # FAISS loader logs AVX capability checks at INFO — noise in production
            "faiss.loader": {
                "handlers": ["console", "app_file", "error_file"],
                "level": "WARNING",
                "propagate": False,
            },
            "faiss": {
                "handlers": ["console", "app_file", "error_file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    log_max_days: Optional[int] = None,
) -> None:
    """
    应用集中式日志配置（幂等，仅首次调用生效）。

    供以下场景使用：
    - app.py 启动时（import 阶段）
    - CLI 工具的 __main__ 块中（analyzer_runner、generate_report 等）
    """
    global _initialized
    if _initialized:
        return

    log_dir, log_level, log_max_days = _resolve_defaults(
        log_dir, log_level, log_max_days
    )
    config = _build_log_config(log_dir, log_level, log_max_days)
    logging.config.dictConfig(config)
    _initialized = True


def get_uvicorn_log_config(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    log_max_days: Optional[int] = None,
) -> dict:
    """
    返回 dictConfig 字典，用于 uvicorn.run(log_config=...)。

    确保 uvicorn 自身的启动/访问/错误日志也写入同一组 handler。
    """
    log_dir, log_level, log_max_days = _resolve_defaults(
        log_dir, log_level, log_max_days
    )
    return _build_log_config(log_dir, log_level, log_max_days)


def add_logger_daily_file(
    logger_name: str,
    log_path: str,
    log_level: Optional[str] = None,
) -> None:
    """
    为指定的命名 logger 附加一个独立的 TimedRotatingFileHandler。

    复用统一的日志格式，确保风格一致。

    参数：
        logger_name:  logger 名称，如 "weixin_push"
        log_path:     完整日志文件路径，如 "logs/weixin_push_20260710.log"
        log_level:    日志级别，默认使用环境变量 LOG_LEVEL
    """
    from logging.handlers import TimedRotatingFileHandler

    from backend.config.config import LOG_LEVEL, LOG_MAX_DAYS

    level = log_level or LOG_LEVEL

    handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=LOG_MAX_DAYS,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(STANDARD_FORMAT, datefmt=STANDARD_DATE_FORMAT)
    )

    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
