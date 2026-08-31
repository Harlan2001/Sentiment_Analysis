"""路由共用的仓储错误映射。"""

from fastapi import HTTPException

from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchCursorError,
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
)


def raise_repository_error(exc: Exception) -> None:
    if isinstance(exc, WorkbenchNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, WorkbenchPermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, WorkbenchConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WorkbenchCursorError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc
