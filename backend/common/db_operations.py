"""业务数据库操作统一门面。

按领域拆分于 db_news / db_analysis / db_factor / db_yield，
本文件仅聚合并保持既有调用方 `from backend.common.db_operations import DBOperations` 兼容。
"""

from backend.common.db_analysis import AnalysisQueries
from backend.common.db_factor import FactorQueries
from backend.common.db_news import NewsQueries
from backend.common.db_yield import YieldQueries


class DBOperations(NewsQueries, AnalysisQueries, FactorQueries, YieldQueries):
    """统一 DB 操作门面（各领域方法见对应基类）。"""
