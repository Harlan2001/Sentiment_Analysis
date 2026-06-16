"""
因子管理模块
负责因子的查询、提示词生成与新增。
"""

from collections import defaultdict
from typing import Set

import pymysql

from backend.config.config import MYSQL_CONFIG


def get_factors_from_db() -> list:
    """从MySQL加载所有因子（使用上下文管理器，自动关闭连接）"""
    try:
        with pymysql.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT code, name, category, factor_type FROM factor ORDER BY category, code")
                return list(cursor.fetchall())
    except Exception as e:
        print(f"❌ 加载因子失败: {e}")
        raise


def get_factor_codes() -> Set[str]:
    """获取所有因子代码"""
    return {f["code"] for f in get_factors_from_db()}


def get_factor_prompt_text() -> str:
    """生成AI可读的因子列表"""
    categorized = defaultdict(list)
    for f in get_factors_from_db():
        categorized[f["category"]].append((f["code"], f["name"], f["factor_type"]))

    lines = []
    for category, factors in categorized.items():
        lines.append(f"\n【{category}】")
        quant = [f"{c}({n})" for c, n, t in factors if t == "quantitative"]
        concept = [f"{c}({n})" for c, n, t in factors if t == "conceptual"]
        if quant:
            lines.append(f"  Quantitative（量化）: {', '.join(quant)}")
        if concept:
            lines.append(f"  Conceptual（非量化）: {', '.join(concept)}")
    return "\n".join(lines)


def add_new_factor(category: str, code: str, name: str, factor_type: str) -> bool:
    """添加新因子（上下文管理器，消除手动close）"""
    if code in get_factor_codes():
        return False
    try:
        with pymysql.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO factor (code, name, category, factor_type) VALUES (%s,%s,%s,%s)",
                    (code, name, category, factor_type),
                )
            conn.commit()
        return True
    except Exception as e:
        print(f"❌ 添加因子失败: {e}")
        return False
