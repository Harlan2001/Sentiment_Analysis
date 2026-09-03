"""路由共用的仓储错误映射。

各域异常统一继承 ``RepositoryError``（声明各自 ``status_code``）后，
此处是唯一的路由层「异常 → HTTPException」入口；
``KeyError``（ai_strategy_generation 曾手写 ``except KeyError`` → 404）一并收敛。
"""

from fastapi import HTTPException

from backend.repositories.base import RepositoryError


def raise_repository_error(exc: Exception) -> None:
    if isinstance(exc, RepositoryError):
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


def strip_to_required(value: str, error_msg: str = "不能为空") -> str:
    """去除首尾空白并校验非空（供各路由 Pydantic ``field_validator`` 复用）。"""
    value = value.strip()
    if not value:
        raise ValueError(error_msg)
    return value


def collapse_whitespace_required(value: str) -> str:
    """压缩连续空白为单空格并校验非空（供各路由 Pydantic ``field_validator`` 复用）。"""
    value = " ".join(value.split())
    if not value:
        raise ValueError("不能为空")
    return value