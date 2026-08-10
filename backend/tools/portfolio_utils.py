"""
投资组合策略工具函数

提供纯数据处理功能，供 portfolio_strategy 及其他模块使用。
本模块中的函数均为无副作用工具函数，不涉及数据库或 LLM 调用。
"""

import hashlib
import re
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Tuple


def to_decimal_2(value: Any) -> float:
    """将任意值转为保留两位小数的 float，采用四舍五入。

    Args:
        value: 待转换的数值（支持 int / float / str / Decimal）

    Returns:
        保留两位小数的浮点数
    """
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


def range_to_datetime_window(target_date: date) -> Tuple[datetime, datetime]:
    """将日期转换为当天的 datetime 起止窗口。

    Args:
        target_date: 目标日期

    Returns:
        (当天 00:00:00, 当天 23:59:59) 元组
    """
    return (
        datetime.combine(target_date, time(0, 0, 0)),
        datetime.combine(target_date, time(23, 59, 59)),
    )


def extract_json_text(content: str) -> str:
    """从 LLM 原始输出中提取 JSON 文本。

    处理 Markdown 代码围栏（```json ... ```）并提取最外层花括号内容。
    若不含花括号则返回空字符串。

    Args:
        content: LLM 返回的原始文本

    Returns:
        提取出的纯 JSON 文本，或空字符串
    """
    text = (content or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    text = text[start : end + 1]
    # 清理尾随逗号等常见 JSON 不合规问题
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def distribution_sum_check(block: Dict[str, Dict[str, float]], block_name: str) -> None:
    """校验分布区间的 min/max 总和约束。

    要求 sum(min) <= 100 且 sum(max) >= 100，不满足时抛出 ValueError。

    Args:
        block: 字典，值为 {"min": float, "max": float}
        block_name: 区块名称，用于错误提示

    Raises:
        ValueError: 总和约束不满足
    """
    min_sum = sum(v["min"] for v in block.values())
    max_sum = sum(v["max"] for v in block.values())
    if min_sum > 100.0:
        raise ValueError(f"{block_name} min 总和必须 <= 100，当前 {min_sum:.2f}")
    if max_sum < 100.0:
        raise ValueError(f"{block_name} max 总和必须 >= 100，当前 {max_sum:.2f}")


def validate_range(node: Dict[str, Any], name: str) -> Dict[str, float]:
    """校验单个 min/max 区间节点，返回规范化后的区间。

    检查字段存在性、范围 0 <= min <= max <= 100，并统一保留两位小数。

    Args:
        node: {"min": number, "max": number} 的原始字典
        name: 字段名，用于错误提示

    Returns:
        {"min": float, "max": float} 规范化后的区间

    Raises:
        ValueError: 字段缺失或取值越界
    """
    if "min" not in node or "max" not in node:
        raise ValueError(f"{name} 缺少 min 或 max 字段")
    min_v = to_decimal_2(node["min"])
    max_v = to_decimal_2(node["max"])
    if min_v < 0 or max_v < 0 or min_v > 100 or max_v > 100:
        raise ValueError(f"{name} 必须满足 0<=min/max<=100")
    if min_v > max_v:
        raise ValueError(f"{name} 必须满足 min<=max")
    return {"min": min_v, "max": max_v}


def build_data_version(latest_news_pub_time: Optional[datetime]) -> str:
    """根据最新新闻发布时间构建数据版本号。

    Args:
        latest_news_pub_time: 最新新闻的发布时间，可为 None

    Returns:
        格式为 YYYYMMDDHH 的版本字符串；若输入为 None 则返回 "none"
    """
    if not isinstance(latest_news_pub_time, datetime):
        return "none"
    return latest_news_pub_time.strftime("%Y%m%d%H")


def build_cache_key(target_news_date: date, model_name: str, data_version: str) -> str:
    """构建缓存键（MD5 哈希）。

    将目标日期、模型名和数据版本组合后取 MD5，用于查询/写入缓存表。

    Args:
        target_news_date: 目标新闻日期
        model_name: 模型名称
        data_version: 数据版本号（由 build_data_version 生成）

    Returns:
        32 位小写十六进制 MD5 字符串
    """
    raw = f"{target_news_date.isoformat()}|{model_name}|schema_v1|{data_version}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    """将 datetime 格式化为 YYYY-MM-DD HH:MM:SS 字符串。

    Args:
        value: datetime 对象，可为 None

    Returns:
        格式化后的日期时间字符串；若输入不是 datetime 则返回 None
    """
    if not isinstance(value, datetime):
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")
