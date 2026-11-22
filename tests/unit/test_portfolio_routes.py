"""研究组合路由的响应壳、参数传递、错误语义和导入导出契约。"""

from copy import deepcopy
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX
from backend.portfolio.csv_io import MAX_IMPORT_BYTES
from backend.repositories.portfolio_repository import (
    PortfolioConflictError,
    PortfolioImportTooLargeError,
    PortfolioNotFoundError,
    PortfolioVersionConflictError,
)
from backend.routers import portfolios

PATH = f"{API_PREFIX}/portfolios"


def detail():
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "组合一",
        "description": None,
        "size_amount": Decimal("100000.00"),
        "as_of_date": "2026-01-01",
        "target_duration": None,
        "status": "active",
        "version": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "holdings_count": 1,
        "invested_weight": Decimal("20"),
        "cash_weight": Decimal("80"),
        "holdings": [
            {
                "id": 9,
                "bond_code": "A",
                "bond_name": "债券A",
                "asset_category": "利率债",
                "weight_pct": Decimal("20"),
                "yield_pct": None,
                "duration_years": Decimal("2.5"),
                "sort_order": 0,
                "note": None,
            }
        ],
        "metrics": {
            "invested_weight": Decimal("20"),
            "cash_weight": Decimal("80"),
            "weighted_duration": Decimal("2.5"),
            "weighted_yield": None,
            "duration_coverage": Decimal("100"),
            "yield_coverage": Decimal("0"),
            "max_holding_weight": Decimal("20"),
            "max_holding_share_of_invested": Decimal("100"),
            "estimated_invested_amount": Decimal("20000.00"),
            "estimated_cash_amount": Decimal("80000.00"),
            "amount_basis": "研究规模估算（人民币元，非市值）",
            "asset_allocations": [],
            "risk_items": [],
        },
    }


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def client(repo, monkeypatch):
    app = FastAPI()

    @app.middleware("http")
    async def test_identity(request, call_next):
        request.state.username = request.headers.get("X-Test-User", "alice")
        return await call_next(request)

    app.include_router(portfolios.router)
    monkeypatch.setattr(portfolios, "_repository", lambda: repo)
    return TestClient(app)


def test_list_uses_username_filters_and_standard_pagination(client, repo):
    repo.list_portfolios.return_value = {"items": [detail()], "total": 23}

    response = client.get(
        PATH,
        params={"include_archived": "true", "page": 2, "page_size": 10},
        headers={"X-Test-User": "bob"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 23
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["total_pages"] == 3
    assert payload["items"][0]["holdings_count"] == 1
    repo.list_portfolios.assert_called_once_with(
        "bob", include_archived=True, page=2, page_size=10
    )


def test_create_returns_detail_with_json_numbers_and_null(client, repo):
    repo.create_portfolio.return_value = detail()
    body = {
        "name": " 组合一 ",
        "description": " ",
        "size_amount": "100000.00",
        "as_of_date": "2026-01-01",
        "target_duration": None,
    }

    response = client.post(PATH, json=body)

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["size_amount"] == 100000.0
    assert isinstance(data["size_amount"], (int, float))
    assert not isinstance(data["size_amount"], str)
    assert data["target_duration"] is None
    assert data["holdings"][0]["weight_pct"] == 20
    assert isinstance(data["holdings"][0]["duration_years"], (int, float))
    assert isinstance(data["metrics"]["weighted_duration"], (int, float))
    assert isinstance(data["metrics"]["invested_weight"], (int, float))
    assert data["holdings"][0]["yield_pct"] is None
    kwargs = repo.create_portfolio.call_args.kwargs
    assert kwargs["name"] == "组合一"
    assert kwargs["description"] is None
    assert kwargs["size_amount"] == Decimal("100000.00")


def test_cross_user_and_missing_resources_have_same_404(client, repo):
    repo.get_portfolio.side_effect = PortfolioNotFoundError("研究组合不存在或当前用户无权访问")

    response = client.get(f"{PATH}/not-owned", headers={"X-Test-User": "stranger"})

    assert response.status_code == 404
    assert response.json()["detail"] == "研究组合不存在或当前用户无权访问"
    assert repo.get_portfolio.call_args.args == ("stranger", "not-owned")


def test_patch_passes_only_explicit_changes_and_expected_version(client, repo):
    repo.update_portfolio.return_value = detail()

    response = client.patch(
        f"{PATH}/p1",
        json={"description": None, "target_duration": "3.25", "expected_version": 7},
    )

    assert response.status_code == 200
    repo.update_portfolio.assert_called_once_with(
        "alice",
        "p1",
        expected_version=7,
        changes={"description": None, "target_duration": Decimal("3.25")},
    )


@pytest.mark.parametrize(
    "body",
    [
        {"expected_version": 1},
        {"name": None, "expected_version": 1},
        {"size_amount": -1, "expected_version": 1},
        {"target_duration": -0.1, "expected_version": 1},
    ],
)
def test_patch_rejects_empty_null_or_invalid_changes(client, repo, body):
    response = client.patch(f"{PATH}/p1", json=body)
    assert response.status_code == 422
    repo.update_portfolio.assert_not_called()


def test_archived_and_version_conflicts_are_both_409_with_chinese_detail(client, repo):
    repo.add_holding.side_effect = PortfolioConflictError("研究组合已归档，当前为只读状态")
    body = {
        "bond_code": "A",
        "bond_name": "债券A",
        "asset_category": "利率债",
        "weight_pct": 10,
        "expected_version": 2,
    }
    archived = client.post(f"{PATH}/p1/holdings", json=body)
    assert archived.status_code == 409
    assert "只读" in archived.json()["detail"]

    repo.add_holding.reset_mock(side_effect=True)
    repo.add_holding.side_effect = PortfolioVersionConflictError("组合版本已变化，请刷新后重试")
    stale = client.post(f"{PATH}/p1/holdings", json=body)
    assert stale.status_code == 409
    assert "版本" in stale.json()["detail"]


def test_holding_input_validation_and_delete_query_version(client, repo):
    invalid = client.post(
        f"{PATH}/p1/holdings",
        json={
            "bond_code": "A",
            "bond_name": "债券A",
            "asset_category": "利率债",
            "weight_pct": 100.000001,
            "expected_version": 1,
        },
    )
    assert invalid.status_code == 422

    invalid_code = client.post(
        f"{PATH}/p1/holdings",
        json={
            "bond_code": "BAD/CODE",
            "bond_name": "债券A",
            "asset_category": "利率债",
            "weight_pct": 10,
            "expected_version": 1,
        },
    )
    assert invalid_code.status_code == 422
    assert "ASCII" in invalid_code.text
    repo.add_holding.assert_not_called()

    repo.delete_holding.return_value = detail()
    deleted = client.delete(f"{PATH}/p1/holdings/9", params={"expected_version": 3})
    assert deleted.status_code == 200
    assert deleted.json()["data"]["id"] == detail()["id"]
    repo.delete_holding.assert_called_once_with(
        "alice", "p1", 9, expected_version=3
    )


def test_reorder_requires_complete_positive_integer_list_shape(client, repo):
    response = client.put(
        f"{PATH}/p1/holdings/order",
        json={"expected_version": 1, "holding_ids": [0, 2]},
    )
    assert response.status_code == 422
    repo.reorder_holdings.assert_not_called()


def test_import_route_reaches_import_handler_with_multipart_mode_and_version(client, repo):
    content = b"\xef\xbb\xbfbond_code,bond_name,asset_category,weight_pct,yield_pct,duration_years,note\n"
    repo.import_holdings.return_value = {
        "imported_count": 0,
        "errors": [{"row": 2, "field": "weight_pct", "message": "权重必须大于 0"}],
        "portfolio": detail(),
    }

    response = client.post(
        f"{PATH}/p1/holdings/import",
        params={"mode": "replace", "expected_version": 7},
        files={"file": ("holdings.csv", content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["imported_count"] == 0
    assert data["errors"][0]["row"] == 2
    assert data["portfolio"]["version"] == 1
    kwargs = repo.import_holdings.call_args.kwargs
    assert kwargs == {
        "expected_version": 7,
        "mode": "replace",
        "content": content,
    }
    assert repo.import_holdings.call_args.args == ("alice", "p1")


def test_import_oversize_maps_to_413_and_read_is_capped(client, repo):
    def reject_large(*args, **kwargs):
        assert len(kwargs["content"]) == MAX_IMPORT_BYTES + 1
        raise PortfolioImportTooLargeError("CSV 文件不能超过 1MB")

    repo.import_holdings.side_effect = reject_large
    response = client.post(
        f"{PATH}/p1/holdings/import",
        params={"expected_version": 1},
        files={"file": ("large.csv", b"x" * (MAX_IMPORT_BYTES + 100), "text/csv")},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "CSV 文件不能超过 1MB"


def test_export_has_bom_safe_content_disposition_and_csv_content_type(client, repo):
    exported = deepcopy(detail())
    exported["name"] = "=bad\r\nContent-Disposition: inline"
    repo.get_portfolio.return_value = exported

    response = client.get(f"{PATH}/p1/export")

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "\r" not in disposition and "\n" not in disposition
    assert "Content-Disposition: inline" not in disposition
    assert "filename*=UTF-8''" in disposition
