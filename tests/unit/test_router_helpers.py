"""Phase 0 共享 helper 的纯逻辑单测（不依赖数据库）。

覆盖：``raise_repository_error`` 泛化映射、``strip_to_required`` /
``collapse_whitespace_required`` 保真语义、``paginated_payload`` / ``total_pages`` /
``offset``、``best_analysis_join`` SQL 片段。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.common.db_analysis import AnalysisQueries
from backend.common.pagination import offset, paginated_payload, total_pages
from backend.repositories.base import RepositoryError
from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
)
from backend.routers.workbench_helpers import (
    collapse_whitespace_required,
    raise_repository_error,
    strip_to_required,
)

# ── raise_repository_error ────────────────────────────────────────────────


def test_repository_error_maps_status_code():
    with pytest.raises(HTTPException) as exc_info:
        raise_repository_error(WorkbenchNotFoundError("未找到"))
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "未找到"


def test_repository_error_respects_custom_status():
    class TeapotError(RepositoryError):
        status_code = 418

    with pytest.raises(HTTPException) as exc_info:
        raise_repository_error(TeapotError("teapot"))
    assert exc_info.value.status_code == 418


def test_keyerror_maps_to_404():
    with pytest.raises(HTTPException) as exc_info:
        raise_repository_error(KeyError("missing_key"))
    assert exc_info.value.status_code == 404


def test_unknown_error_reraised():
    with pytest.raises(RuntimeError):
        raise_repository_error(RuntimeError("boom"))


def test_workbench_conflict_maps_409():
    with pytest.raises(HTTPException) as exc_info:
        raise_repository_error(WorkbenchConflictError("冲突"))
    assert exc_info.value.status_code == 409


# ── 文本校验 helper ───────────────────────────────────────────────────────


def test_strip_to_required_trims():
    assert strip_to_required("  hi  ") == "hi"


def test_strip_to_required_empty_raises_default_msg():
    with pytest.raises(ValueError, match="不能为空"):
        strip_to_required("   ")


def test_strip_to_required_custom_msg():
    with pytest.raises(ValueError, match="Cannot be empty"):
        strip_to_required("  ", "Cannot be empty")


def test_collapse_whitespace_required():
    assert collapse_whitespace_required("  a   b  ") == "a b"


def test_collapse_whitespace_required_empty_raises():
    with pytest.raises(ValueError, match="不能为空"):
        collapse_whitespace_required(" \t ")


# ── 分页工具 ──────────────────────────────────────────────────────────────


def test_offset():
    assert offset(1, 20) == 0
    assert offset(3, 10) == 20


def test_total_pages():
    assert total_pages(0, 10) == 0
    assert total_pages(10, 10) == 1
    assert total_pages(23, 10) == 3


def test_paginated_payload_shape():
    payload = paginated_payload(["a", "b"], total=23, page=2, page_size=10)
    assert payload == {
        "items": ["a", "b"],
        "total": 23,
        "page": 2,
        "page_size": 10,
        "total_pages": 3,
    }


# ── best-analysis JOIN 片段 ───────────────────────────────────────────────


def test_best_analysis_join_left_default():
    sql = AnalysisQueries.best_analysis_join()
    assert sql.startswith("LEFT JOIN analysis a")
    assert "ELSE 999" in sql
    assert "LIMIT 1" in sql


def test_best_analysis_join_inner():
    assert AnalysisQueries.best_analysis_join("JOIN").startswith("JOIN analysis a")