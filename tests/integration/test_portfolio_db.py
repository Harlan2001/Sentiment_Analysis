"""研究组合的真实 MySQL CRUD、隔离、版本、导入与事务回滚测试。"""

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX
from backend.repositories.portfolio_repository import (
    PortfolioRepository,
    PortfolioVersionConflictError,
)
from backend.routers import portfolios

pytestmark = pytest.mark.integration
PATH = f"{API_PREFIX}/portfolios"
HEADER = "bond_code,bond_name,asset_category,weight_pct,yield_pct,duration_years,note\n"


@pytest.fixture(autouse=True)
def _clean(mysql_conn, clean_tables):
    # DDL 由主代理/CI 预先执行；本测试不创建表、不执行迁移。
    with mysql_conn.cursor() as cursor:
        for table in ("research_portfolios", "research_portfolio_holdings"):
            cursor.execute("SHOW TABLES LIKE %s", (table,))
            if not cursor.fetchone():
                pytest.skip(f"测试库尚未包含 {table}，请先由主流程执行 DDL")
    clean_tables("research_portfolio_holdings", "research_portfolios")


@pytest.fixture
def client():
    app = FastAPI()

    @app.middleware("http")
    async def test_identity(request, call_next):
        request.state.username = request.headers.get("X-Test-User", "alice")
        return await call_next(request)

    app.include_router(portfolios.router)
    return TestClient(app)


def create_portfolio(client, name="研究组合", user="alice"):
    response = client.post(
        PATH,
        headers={"X-Test-User": user},
        json={
            "name": name,
            "description": "真实测试库",
            "size_amount": "100000.00",
            "as_of_date": "2026-01-01",
            "target_duration": "3.0000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def holding_body(code, weight, version, *, duration="3", yield_pct="2.5"):
    return {
        "bond_code": code,
        "bond_name": f"债券{code}",
        "asset_category": "利率债",
        "weight_pct": str(weight),
        "yield_pct": yield_pct,
        "duration_years": duration,
        "note": None,
        "expected_version": version,
    }


def get_detail(client, portfolio_id, user="alice"):
    response = client.get(f"{PATH}/{portfolio_id}", headers={"X-Test-User": user})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def import_csv(client, portfolio_id, content, version, mode="append"):
    response = client.post(
        f"{PATH}/{portfolio_id}/holdings/import",
        params={"expected_version": version, "mode": mode},
        files={"file": ("holdings.csv", content.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_real_db_crud_ownership_versions_archive_restore_and_export(client):
    created = create_portfolio(client)
    portfolio_id = created["id"]
    assert created["version"] == 1
    assert created["metrics"]["cash_weight"] == 100
    assert created["metrics"]["weighted_duration"] is None

    first = client.post(
        f"{PATH}/{portfolio_id}/holdings",
        json=holding_body("A", 60, 1, duration=None, yield_pct=None),
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["version"] == 2
    holding_a = first.json()["data"]["holdings"][0]
    assert isinstance(holding_a["id"], int)
    assert holding_a["sort_order"] == 0

    second = client.post(
        f"{PATH}/{portfolio_id}/holdings",
        json=holding_body("B", 40, 2, duration="4", yield_pct="3"),
    )
    assert second.status_code == 201, second.text
    assert second.json()["data"]["version"] == 3
    holding_b = next(
        row for row in second.json()["data"]["holdings"] if row["bond_code"] == "B"
    )

    stale = client.post(
        f"{PATH}/{portfolio_id}/holdings",
        json=holding_body("STALE", 1, 2),
    )
    assert stale.status_code == 409
    assert get_detail(client, portfolio_id)["holdings_count"] == 2

    patched = client.patch(
        f"{PATH}/{portfolio_id}",
        json={"name": "更新后的组合", "expected_version": 3},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["version"] == 4

    patched_holding = client.patch(
        f"{PATH}/{portfolio_id}/holdings/{holding_a['id']}",
        json={"weight_pct": "30", "expected_version": 4},
    )
    assert patched_holding.status_code == 200, patched_holding.text
    detail_after_patch = patched_holding.json()["data"]
    assert detail_after_patch["version"] == 5
    assert detail_after_patch["invested_weight"] == 70
    assert detail_after_patch["metrics"]["duration_coverage"] == pytest.approx(40 / 70 * 100)

    reordered = client.put(
        f"{PATH}/{portfolio_id}/holdings/order",
        json={"expected_version": 5, "holding_ids": [holding_b["id"], holding_a["id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [row["bond_code"] for row in reordered.json()["data"]["holdings"]] == ["B", "A"]
    assert reordered.json()["data"]["version"] == 6

    deleted = client.delete(
        f"{PATH}/{portfolio_id}/holdings/{holding_b['id']}",
        params={"expected_version": 6},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["version"] == 7
    assert deleted.json()["data"]["holdings_count"] == 1

    archived = client.post(
        f"{PATH}/{portfolio_id}/archive", json={"expected_version": 7}
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    assert archived.json()["data"]["version"] == 8

    read_only = client.patch(
        f"{PATH}/{portfolio_id}",
        json={"name": "不可写", "expected_version": 8},
    )
    assert read_only.status_code == 409
    default_list = client.get(PATH).json()["data"]
    full_list = client.get(PATH, params={"include_archived": True}).json()["data"]
    assert default_list["total"] == 0
    assert full_list["total"] == 1
    assert full_list["items"][0]["holdings_count"] == 1
    assert full_list["items"][0]["invested_weight"] == 30

    restored = client.post(
        f"{PATH}/{portfolio_id}/restore", json={"expected_version": 8}
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "active"
    assert restored.json()["data"]["version"] == 9

    for response in (
        client.get(f"{PATH}/{portfolio_id}", headers={"X-Test-User": "bob"}),
        client.patch(
            f"{PATH}/{portfolio_id}",
            headers={"X-Test-User": "bob"},
            json={"name": "越权", "expected_version": 9},
        ),
        client.get(f"{PATH}/00000000-0000-0000-0000-000000000000"),
    ):
        assert response.status_code == 404, response.text

    exported = client.get(f"{PATH}/{portfolio_id}/export")
    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert ["组合ID", portfolio_id] in rows
    assert any(row and row[0] == "invested_weight" for row in rows)


def test_real_db_copy_and_import_are_atomic_and_versioned(client, monkeypatch):
    created = create_portfolio(client, "导入组合")
    portfolio_id = created["id"]
    initial = (
        HEADER
        + "A,债券A,利率债,30,2.5,2,\n"
        + "B,债券B,信用债,20,3.5,4,\n"
    )
    imported = import_csv(client, portfolio_id, initial, 1)
    assert imported["imported_count"] == 2
    assert imported["errors"] == []
    assert imported["portfolio"]["version"] == 2

    duplicate = import_csv(
        client,
        portfolio_id,
        HEADER + "a,重复代码,利率债,1,2,1,\n",
        2,
    )
    assert duplicate["imported_count"] == 0
    assert duplicate["errors"][0]["field"] == "bond_code"
    assert duplicate["portfolio"]["version"] == 2
    assert duplicate["portfolio"]["holdings_count"] == 2

    invalid = import_csv(
        client,
        portfolio_id,
        HEADER + "C,债券C,利率债,10,2,1,\nD,债券D,利率债,0,2,1,\n",
        2,
        mode="replace",
    )
    assert invalid["imported_count"] == 0
    assert invalid["errors"]
    assert {row["bond_code"] for row in invalid["portfolio"]["holdings"]} == {"A", "B"}
    assert invalid["portfolio"]["version"] == 2

    # 强制在 replace 已删除旧持仓、插入新持仓之后抛错，验证真实事务回滚。
    repository = PortfolioRepository.from_environment()
    replacement = (
        HEADER
        + "C,债券C,利率债,30,2.5,2,\n"
        + "D,债券D,信用债,20,3.5,4,\n"
    ).encode("utf-8-sig")
    with monkeypatch.context() as patch:
        def fail_bump(*args, **kwargs):
            raise RuntimeError("forced rollback after replace writes")

        patch.setattr(PortfolioRepository, "_bump_version", staticmethod(fail_bump))
        with pytest.raises(RuntimeError, match="forced rollback"):
            repository.import_holdings(
                "alice",
                portfolio_id,
                expected_version=2,
                mode="replace",
                content=replacement,
            )
    after_rollback = repository.get_portfolio("alice", portfolio_id)
    assert after_rollback["version"] == 2
    assert {row["bond_code"] for row in after_rollback["holdings"]} == {"A", "B"}

    replaced = import_csv(client, portfolio_id, replacement.decode("utf-8-sig"), 2, "replace")
    assert replaced["imported_count"] == 2
    assert replaced["portfolio"]["version"] == 3
    assert {row["bond_code"] for row in replaced["portfolio"]["holdings"]} == {"C", "D"}

    excess = import_csv(
        client,
        portfolio_id,
        HEADER + "E,债券E,利率债,60,2,1,\n",
        3,
    )
    assert excess["imported_count"] == 0
    assert excess["errors"][0]["field"] == "weight_pct"
    assert excess["portfolio"]["version"] == 3

    copied_response = client.post(f"{PATH}/{portfolio_id}/copy", json={"name": "组合副本"})
    assert copied_response.status_code == 201, copied_response.text
    copied = copied_response.json()["data"]
    assert copied["version"] == 1
    assert copied["status"] == "active"
    assert copied["holdings_count"] == 2
    assert [row["bond_code"] for row in copied["holdings"]] == ["C", "D"]
    assert {row["id"] for row in copied["holdings"]}.isdisjoint(
        {row["id"] for row in get_detail(client, portfolio_id)["holdings"]}
    )
    assert get_detail(client, portfolio_id)["version"] == 3


def test_real_db_parent_lock_serializes_optimistic_writes(client):
    created = create_portfolio(client, "并发组合")
    portfolio_id = created["id"]
    repository = PortfolioRepository.from_environment()

    def add(code):
        try:
            repository.add_holding(
                "alice",
                portfolio_id,
                expected_version=1,
                holding={
                    "bond_code": code,
                    "bond_name": f"债券{code}",
                    "asset_category": "利率债",
                    "weight_pct": 30,
                    "yield_pct": None,
                    "duration_years": None,
                    "note": None,
                },
            )
            return "ok"
        except PortfolioVersionConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(add, ("LOCK_A", "LOCK_B")))

    assert sorted(outcomes) == ["conflict", "ok"]
    final = get_detail(client, portfolio_id)
    assert final["version"] == 2
    assert final["holdings_count"] == 1
