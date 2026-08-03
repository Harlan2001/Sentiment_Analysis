"""
新闻分析模块
提供批量新闻分析功能
"""

from backend.analysis.result_processor import AnalysisResultProcessor as AnalysisResultProcessor
from backend.common.db_operations import DBOperations as DBOperations

__all__ = [
    "AnalysisResultProcessor",
    "DBOperations",
]