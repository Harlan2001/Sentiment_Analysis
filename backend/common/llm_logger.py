"""
LLM Token 使用日志 — 异步写入工具

在所有 LLM 调用点（chat / analysis / strategy / change）复用此模块，
将每次调用的 token 消耗、延迟、成功/失败信息写入 llm_usage_log 表。
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from backend.common.database import execute_update

logger = logging.getLogger("llm_logger")

# 系统级调用的默认用户标识
SYSTEM_USER_ID = 0
SYSTEM_USERNAME = "system"

_table_checked = False
_table_lock = threading.Lock()

_LLM_USAGE_LOG_DDL = """CREATE TABLE IF NOT EXISTS `llm_usage_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL DEFAULT 0 COMMENT '用户ID，系统调用为0',
  `username` varchar(100) NOT NULL DEFAULT 'system' COMMENT '用户名',
  `call_source` varchar(50) NOT NULL COMMENT '调用来源: chat/analysis/strategy/change',
  `model_name` varchar(128) NOT NULL COMMENT '模型名称',
  `provider_model` varchar(255) DEFAULT NULL COMMENT 'provider完整模型名',
  `prompt_tokens` int(11) NOT NULL DEFAULT 0,
  `completion_tokens` int(11) NOT NULL DEFAULT 0,
  `total_tokens` int(11) NOT NULL DEFAULT 0,
  `request_id` varchar(128) DEFAULT NULL,
  `success` tinyint(1) NOT NULL DEFAULT 1,
  `error_message` text COMMENT '失败原因',
  `latency_ms` int(10) unsigned DEFAULT NULL COMMENT '请求耗时(ms)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_date` (`user_id`, `created_at`),
  KEY `idx_call_source` (`call_source`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM调用Token消耗日志'"""


def _ensure_table() -> None:
    """首次调用时自动创建 llm_usage_log 表（幂等）"""
    global _table_checked
    if _table_checked:
        return
    with _table_lock:
        if _table_checked:
            return
        try:
            execute_update(_LLM_USAGE_LOG_DDL)
            logger.info("llm_usage_log 表已就绪")
        except Exception:
            logger.exception("llm_usage_log 表创建失败，Token 记录将不可用")
        _table_checked = True


def log_llm_usage(
    *,
    user_id: int = SYSTEM_USER_ID,
    username: str = SYSTEM_USERNAME,
    call_source: str,
    model_name: str,
    provider_model: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    success: bool = True,
    error_message: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> None:
    """写入 LLM 调用日志（自动建表，失败不影响主流程）"""
    _ensure_table()
    try:
        execute_update(
            """INSERT INTO llm_usage_log
            (user_id, username, call_source, model_name, provider_model,
             prompt_tokens, completion_tokens, total_tokens, success, error_message, latency_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                user_id,
                username,
                call_source,
                model_name,
                provider_model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                1 if success else 0,
                (error_message or "")[:1000] if error_message else None,
                latency_ms,
            ),
        )
    except Exception as e:
        logger.warning("LLM usage log 写入失败: %s", str(e)[:200])
