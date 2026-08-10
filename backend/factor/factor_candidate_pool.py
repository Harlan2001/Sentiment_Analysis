"""
新因子自动发现模块
相似度低于阈值时自动加入标准因子库，无需人工审核
"""

import logging
import sys
from datetime import datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pymysql

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.config.config import MYSQL_CONFIG  # noqa: E402
from backend.factor.factor_management import add_new_factor  # noqa: E402
from backend.factor.factor_similarity import get_similarity_engine  # noqa: E402

logger = logging.getLogger(__name__)


def _convert_numpy_types(obj):
    """递归转换numpy类型为Python原生类型"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, Integral):
        return int(obj)
    elif isinstance(obj, Real):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj


class FactorDiscoveryManager:
    """
    新因子发现管理器
    自动判断是否为新因子，低于阈值直接加入标准库
    """

    SIMILARITY_THRESHOLD = 0.7  # 相似度阈值，低于此值判定为新因子

    def __init__(self, mysql_config: dict = MYSQL_CONFIG):
        self.mysql_config = mysql_config
        self.similarity_engine = get_similarity_engine()

    def process_new_factor(
        self,
        factor_data: Dict[str, Any],
        source_news_id: int,
        extracted_text: str,
        model_name: str,
        conn: Optional[pymysql.connections.Connection] = None,
    ) -> Dict[str, Any]:
        """
        处理新发现的因子
        相似度低于阈值自动加入标准库，否则直接丢弃

        Args:
            factor_data: 因子数据字典
            source_news_id: 来源新闻ID
            extracted_text: 提取的原始文本
            model_name: 创建该因子的模型名称
            conn: 可选的外部数据库连接

        Returns:
            处理结果字典
        """
        # 进行相似度分析
        similarity_results = self.similarity_engine.calculate_similarity(
            f"{factor_data.get('name', '')} {factor_data.get('code', '')}", top_k=1
        )

        # 获取最佳匹配
        best_match = similarity_results[0] if similarity_results else None
        max_similarity = best_match.similarity_score if best_match else 0.0

        factor_code = factor_data.get("code", "")
        factor_name = factor_data.get("name", "")

        result = {
            "code": factor_code,
            "name": factor_name,
            "max_similarity": max_similarity,
            "best_match": (
                {"code": best_match.factor_code, "name": best_match.factor_name}
                if best_match
                else None
            ),
            "action": "",
            "success": False,
        }

        # 记录发现历史
        best_match_code = best_match.factor_code if best_match else None
        best_match_code_str = best_match.factor_code if best_match else "None"

        self._log_discovery_history(
            factor_data=factor_data,
            source_news_id=source_news_id,
            extracted_text=extracted_text,
            model_name=model_name,
            max_similarity=max_similarity,
            best_match_code=best_match_code,
            conn=conn,
        )

        if max_similarity < self.SIMILARITY_THRESHOLD:
            # 低相似度，加入标准因子库
            add_success = add_new_factor(
                category=factor_data["category"],
                code=factor_data["code"],
                name=factor_data["name"],
                factor_type=factor_data["type"],
            )
            if add_success:
                # 重载相似度引擎的因子库
                self.similarity_engine.reload_factors()

                result["action"] = "added_to_standard_library"
                result["success"] = True
                logger.info(
                    "新因子已加入标准库: %s (%s), 相似度: %.3f",
                    factor_code,
                    factor_name,
                    max_similarity,
                )
            else:
                result["action"] = "already_exists"
                result["success"] = False
                logger.debug("因子已存在: %s (%s)", factor_code, factor_name)
        else:
            # 高相似度，丢弃
            result["action"] = "discarded_duplicate"
            result["success"] = False
            logger.debug(
                "因子重复已丢弃: %s (%s), 与 %s 相似度: %.3f",
                factor_code,
                factor_name,
                best_match_code_str,
                max_similarity,
            )

        return result

    def _log_discovery_history(
        self,
        factor_data: Dict[str, Any],
        source_news_id: int,
        extracted_text: str,
        model_name: str,
        max_similarity: float,
        best_match_code: Optional[str],
        conn: Optional[pymysql.connections.Connection] = None,
    ):
        """记录因子发现历史"""
        external_conn = conn is not None
        if conn is None:
            conn = pymysql.connect(**self.mysql_config)
        try:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO factor_discovery_history
                (code, name, category, factor_type, description,
                 source_news_id, extracted_text, created_by_model,
                 max_similarity_score, most_similar_factor_code,
                 created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    factor_data.get("code", ""),
                    factor_data.get("name", ""),
                    factor_data.get("category", ""),
                    factor_data.get("type", ""),
                    factor_data.get("logic_impact", ""),
                    source_news_id,
                    extracted_text,
                    model_name,
                    max_similarity,
                    best_match_code,
                    datetime.now().isoformat(),
                ),
            )

            if not external_conn:
                conn.commit()
        finally:
            if not external_conn:
                conn.close()


# 全局单例实例
_discovery_manager = None


def get_factor_discovery_manager() -> FactorDiscoveryManager:
    """获取因子发现管理器单例"""
    global _discovery_manager
    if _discovery_manager is None:
        _discovery_manager = FactorDiscoveryManager()
    return _discovery_manager
