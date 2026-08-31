"""因子与新闻-因子关联数据操作。"""

from datetime import datetime
from typing import Any, Dict, Optional

from backend.common.database import get_db_connection


class FactorQueries:
    """因子与新闻-因子关联操作。"""

    @staticmethod
    def get_factor_id_by_code(factor_code: str) -> Optional[int]:
        """
        根据因子代码获取因子ID

        Args:
            factor_code: 因子代码

        Returns:
            因子ID，如果不存在返回None
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM factor WHERE code = %s
                """,
                    (factor_code,),
                )
                result = cur.fetchone()
                return result[0] if result else None
    @staticmethod
    def save_news_factor_relation(
        news_id: int, factor_id: int, factor_data: Dict[str, Any], model: str, conn: Any
    ) -> bool:
        """
        保存新闻与因子的关联关系到news_factor表

        Args:
            news_id: 新闻ID
            factor_id: 因子ID
            factor_data: 因子数据字典
            model: 模型名称
            conn: 数据库连接（必须提供，用于事务）

        Returns:
            是否保存成功
        """
        try:
            with conn.cursor() as cur:
                direction = factor_data.get("direction", "neutral")
                logic_impact = factor_data.get("logic_impact", "")

                # 查询新闻发布时间用于冗余存储
                cur.execute("SELECT pub_time FROM news WHERE id = %s", (news_id,))
                row = cur.fetchone()
                pub_time = row[0] if row else None

                cur.execute(
                    """
                    INSERT INTO news_factor
                    (news_id, factor_id, direction, driver, model, created_at, pub_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        direction = VALUES(direction),
                        driver = VALUES(driver),
                        model = VALUES(model),
                        created_at = VALUES(created_at),
                        pub_time = VALUES(pub_time)
                """,
                    (
                        news_id,
                        factor_id,
                        direction,
                        logic_impact,
                        model,
                        datetime.now(),
                        pub_time,
                    ),
                )

            return True
        except Exception as e:
            raise e
