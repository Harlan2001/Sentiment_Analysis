"""
分析结果处理器
处理分析结果中的因子，包括相似度检查、新因子发现和关联关系保存
"""

import logging
from typing import Any, Dict, List, Optional

from backend.common.db_operations import DBOperations
from backend.factor.factor_candidate_pool import get_factor_discovery_manager

logger = logging.getLogger(__name__)


class AnalysisResultProcessor:
    """
    分析结果处理器
    负责处理分析结果中的因子，包括：
    1. 因子相似度检查
    2. 新因子自动发现和入库
    3. 新闻-因子关联关系保存
    """

    def __init__(self, model_name: str = "kingstar"):
        self.model_name = model_name
        self.discovery_manager = get_factor_discovery_manager()
        self.db_ops = DBOperations()

    def process_analysis_result(
        self, news_id: int, analysis_result: Dict[str, Any], conn: Any
    ) -> bool:
        """
        处理完整的分析结果，包括主因子和次要因子

        Args:
            news_id: 新闻ID
            analysis_result: 分析结果字典
            conn: 数据库连接（用于事务）

        Returns:
            是否处理成功
        """
        try:
            factors = analysis_result.get("factors", [])

            if factors:
                self._process_factor_list(news_id=news_id, factors=factors, conn=conn)

            return True

        except Exception as e:
            logger.error(f"处理新闻{news_id}的因子结果失败: {str(e)}", exc_info=True)
            raise e

    def _process_factor_list(
        self, news_id: int, factors: List[Dict[str, Any]], conn: Any
    ) -> List[int]:
        """
        处理因子列表，返回成功处理的因子ID列表

        Args:
            news_id: 新闻ID
            factors: 因子列表
            conn: 数据库连接

        Returns:
            因子ID列表
        """
        factor_ids = []

        for factor_data in factors:
            try:
                factor_id = self._process_single_factor(
                    news_id=news_id, factor_data=factor_data, conn=conn
                )
                if factor_id:
                    factor_ids.append(factor_id)
            except Exception as e:
                logger.error(
                    f"处理新闻{news_id}的因子{factor_data.get('code')}失败: {str(e)}",
                    exc_info=True,
                )
                # 单个因子处理失败不影响其他因子
                continue

        return factor_ids

    def _process_single_factor(
        self, news_id: int, factor_data: Dict[str, Any], conn: Any
    ) -> Optional[int]:
        """
        处理单个因子，包括：
        1. 检查是否为新因子
        2. 新因子自动入库
        3. 保存新闻-因子关联关系

        Args:
            news_id: 新闻ID
            factor_data: 因子数据字典
            conn: 数据库连接

        Returns:
            因子ID，如果处理失败返回None
        """
        factor_code = factor_data.get("code", "")
        factor_name = factor_data.get("name", "")

        if not factor_code:
            logger.warning(f"新闻{news_id}的因子缺少code字段，跳过处理")
            return None

        # 检查因子是否已经存在
        factor_id = self.db_ops.get_factor_id_by_code(factor_code)

        # 处理新因子
        if factor_data.get("is_new_discovery", False) or not factor_id:
            # 补全缺失字段
            if "name" not in factor_data or not factor_data["name"]:
                # 从code生成中文名称（大写转中文，下划线转空格）
                factor_data["name"] = factor_data["code"].replace("_", " ").title()

            # 构建因子文本描述
            factor_text = f"{factor_data['name']} {factor_code}"

            # 处理新因子
            discovery_result = self.discovery_manager.process_new_factor(
                factor_data=factor_data,
                source_news_id=news_id,
                extracted_text=factor_text,
                model_name=self.model_name,
                conn=conn,
            )

            # 重新获取因子ID
            factor_id = self.db_ops.get_factor_id_by_code(factor_code)

            if not factor_id:
                logger.error(
                    f"因子{factor_code}({factor_name})处理后仍不存在，跳过关联"
                )
                return None

            logger.info(f"因子{factor_code}处理结果: {discovery_result.get('action')}")

        # 保存新闻与因子的关联关系
        try:
            self.db_ops.save_news_factor_relation(
                news_id=news_id,
                factor_id=factor_id,
                factor_data=factor_data,
                model=self.model_name,
                conn=conn,
            )
            return factor_id
        except Exception as e:
            logger.error(
                f"保存新闻{news_id}与因子{factor_code}的关联关系失败: {str(e)}"
            )
            raise e

    def validate_analysis_result(self, analysis_result: Dict[str, Any]) -> bool:
        """
        验证分析结果的有效性

        Args:
            analysis_result: 分析结果字典

        Returns:
            是否有效
        """
        required_fields = ["direction", "horizon", "reason", "factors"]

        for field in required_fields:
            if field not in analysis_result:
                logger.warning(f"分析结果缺少必填字段: {field}")
                return False

        return True
