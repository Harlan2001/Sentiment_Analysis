"""账号级研究组合与持仓的事务化持久化访问。"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from backend.common.pagination import offset
from backend.portfolio.csv_io import (
    CsvImportFormatError,
    CsvImportTooLargeError,
    parse_holdings_csv,
)
from backend.portfolio.metrics import calculate_portfolio_metrics
from backend.repositories.base import BaseRepository, RepositoryError, serialize_row

HUNDRED = Decimal("100")
ZERO = Decimal("0")
HOLDING_FIELDS = (
    "bond_code",
    "bond_name",
    "asset_category",
    "weight_pct",
    "yield_pct",
    "duration_years",
    "note",
)


class PortfolioValidationError(RepositoryError):
    status_code = 400


class PortfolioNotFoundError(RepositoryError):
    status_code = 404


class PortfolioConflictError(RepositoryError):
    status_code = 409


class PortfolioVersionConflictError(PortfolioConflictError):
    """expected_version 已过期。"""


class PortfolioImportTooLargeError(RepositoryError):
    status_code = 413


class PortfolioRepository(BaseRepository):
    """所有写操作锁定父组合，统一执行归属、状态与版本校验。"""

    @staticmethod
    def _lock_portfolio(
        cursor: Any,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int | None = None,
        require_active: bool = True,
    ) -> dict[str, Any]:
        cursor.execute(
            """SELECT * FROM research_portfolios
               WHERE id = %s AND owner_username = %s FOR UPDATE""",
            (portfolio_id, username),
        )
        portfolio = cursor.fetchone()
        if not portfolio:
            raise PortfolioNotFoundError("研究组合不存在或当前用户无权访问")
        if expected_version is not None and int(portfolio["version"]) != expected_version:
            raise PortfolioVersionConflictError("组合版本已变化，请刷新后重试")
        if require_active and portfolio["status"] != "active":
            raise PortfolioConflictError("研究组合已归档，当前为只读状态")
        return portfolio

    @staticmethod
    def _bump_version(cursor: Any, username: str, portfolio_id: str, version: int) -> None:
        affected = cursor.execute(
            """UPDATE research_portfolios
               SET version = version + 1, updated_at = CURRENT_TIMESTAMP(6)
               WHERE id = %s AND owner_username = %s AND version = %s""",
            (portfolio_id, username, version),
        )
        if affected != 1:
            raise PortfolioVersionConflictError("组合版本已变化，请刷新后重试")

    @staticmethod
    def _holding_rows(cursor: Any, portfolio_id: str) -> list[dict[str, Any]]:
        cursor.execute(
            """SELECT id, bond_code, bond_name, asset_category, weight_pct,
                      yield_pct, duration_years, sort_order, note,
                      created_at, updated_at
               FROM research_portfolio_holdings
               WHERE portfolio_id = %s ORDER BY sort_order ASC, id ASC""",
            (portfolio_id,),
        )
        return list(cursor.fetchall())

    @staticmethod
    def _serialize_holding(row: dict[str, Any]) -> dict[str, Any]:
        serialized = serialize_row(row) or {}
        return {
            field: serialized.get(field)
            for field in (
                "id",
                "bond_code",
                "bond_name",
                "asset_category",
                "weight_pct",
                "yield_pct",
                "duration_years",
                "sort_order",
                "note",
            )
        }

    @staticmethod
    def _summary(
        portfolio: dict[str, Any],
        *,
        holdings_count: int,
        invested_weight: Decimal,
    ) -> dict[str, Any]:
        row = serialize_row(portfolio) or {}
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description"),
            "size_amount": row["size_amount"],
            "as_of_date": row["as_of_date"],
            "target_duration": row.get("target_duration"),
            "status": row["status"],
            "version": int(row["version"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "holdings_count": int(holdings_count),
            "invested_weight": invested_weight,
            "cash_weight": HUNDRED - invested_weight,
        }

    def list_portfolios(
        self,
        username: str,
        *,
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        where = "owner_username = %s"
        params: list[Any] = [username]
        if not include_archived:
            where += " AND status = 'active'"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM research_portfolios WHERE {where}",
                    tuple(params),
                )
                total = int((cursor.fetchone() or {}).get("total") or 0)
                if total == 0:
                    return {"items": [], "total": 0}
                cursor.execute(
                    f"""SELECT * FROM research_portfolios
                        WHERE {where} ORDER BY updated_at DESC, id DESC
                        LIMIT %s OFFSET %s""",
                    (*params, page_size, offset(page, page_size)),
                )
                portfolios = list(cursor.fetchall())
                if not portfolios:
                    return {"items": [], "total": total}
                portfolio_ids = [row["id"] for row in portfolios]
                placeholders = ",".join(["%s"] * len(portfolio_ids))
                cursor.execute(
                    f"""SELECT portfolio_id, COUNT(*) AS holdings_count,
                               COALESCE(SUM(weight_pct), 0) AS invested_weight
                        FROM research_portfolio_holdings
                        WHERE portfolio_id IN ({placeholders})
                        GROUP BY portfolio_id""",
                    tuple(portfolio_ids),
                )
                stats = {row["portfolio_id"]: row for row in cursor.fetchall()}

        items = []
        for portfolio in portfolios:
            stat = stats.get(portfolio["id"], {})
            invested = stat.get("invested_weight") or ZERO
            items.append(
                self._summary(
                    portfolio,
                    holdings_count=int(stat.get("holdings_count") or 0),
                    invested_weight=invested,
                )
            )
        return {"items": items, "total": total}

    def get_portfolio(self, username: str, portfolio_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT * FROM research_portfolios
                       WHERE id = %s AND owner_username = %s""",
                    (portfolio_id, username),
                )
                portfolio = cursor.fetchone()
                if not portfolio:
                    raise PortfolioNotFoundError("研究组合不存在或当前用户无权访问")
                holdings = self._holding_rows(cursor, portfolio_id)

        serialized_holdings = [self._serialize_holding(row) for row in holdings]
        invested = sum(
            (row["weight_pct"] for row in serialized_holdings), ZERO
        )
        detail = self._summary(
            portfolio,
            holdings_count=len(serialized_holdings),
            invested_weight=invested,
        )
        detail["holdings"] = serialized_holdings
        detail["metrics"] = calculate_portfolio_metrics(
            serialized_holdings,
            size_amount=portfolio["size_amount"],
            target_duration=portfolio.get("target_duration"),
        )
        return detail

    def create_portfolio(
        self,
        username: str,
        *,
        name: str,
        description: str | None,
        size_amount: Decimal,
        as_of_date: Any,
        target_duration: Decimal | None,
    ) -> dict[str, Any]:
        portfolio_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO research_portfolios
                         (id, owner_username, name, description, size_amount,
                          as_of_date, target_duration, status, version)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', 1)""",
                    (
                        portfolio_id,
                        username,
                        name,
                        description,
                        size_amount,
                        as_of_date,
                        target_duration,
                    ),
                )
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def update_portfolio(
        self,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {"name", "description", "size_amount", "as_of_date", "target_duration"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                if updates:
                    assignments = ", ".join(f"{field} = %s" for field in updates)
                    cursor.execute(
                        f"UPDATE research_portfolios SET {assignments} WHERE id = %s",
                        (*updates.values(), portfolio_id),
                    )
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def copy_portfolio(
        self,
        username: str,
        portfolio_id: str,
        *,
        name: str | None = None,
    ) -> dict[str, Any]:
        """在源组合父行锁下复制持仓；源组合不被修改，副本版本从 1 开始。"""
        copy_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                source = self._lock_portfolio(cursor, username, portfolio_id)
                suffix = " - 副本"
                copy_name = name or (source["name"][: 128 - len(suffix)] + suffix)
                cursor.execute(
                    """INSERT INTO research_portfolios
                         (id, owner_username, name, description, size_amount,
                          as_of_date, target_duration, status, version)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', 1)""",
                    (
                        copy_id,
                        username,
                        copy_name,
                        source.get("description"),
                        source["size_amount"],
                        source["as_of_date"],
                        source.get("target_duration"),
                    ),
                )
                holdings = self._holding_rows(cursor, portfolio_id)
                if holdings:
                    cursor.executemany(
                        """INSERT INTO research_portfolio_holdings
                             (portfolio_id, bond_code, bond_name, asset_category,
                              weight_pct, yield_pct, duration_years, sort_order, note)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        [
                            (
                                copy_id,
                                row["bond_code"],
                                row["bond_name"],
                                row["asset_category"],
                                row["weight_pct"],
                                row.get("yield_pct"),
                                row.get("duration_years"),
                                row["sort_order"],
                                row.get("note"),
                            )
                            for row in holdings
                        ],
                    )
            conn.commit()
        return self.get_portfolio(username, copy_id)

    def _change_status(
        self,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int,
        target_status: Literal["active", "archived"],
    ) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                    require_active=False,
                )
                if target_status == "archived":
                    if portfolio["status"] != "active":
                        raise PortfolioConflictError("研究组合已归档，请勿重复归档")
                    cursor.execute(
                        """UPDATE research_portfolios
                           SET status = 'archived', archived_at = CURRENT_TIMESTAMP(6)
                           WHERE id = %s""",
                        (portfolio_id,),
                    )
                else:
                    if portfolio["status"] != "archived":
                        raise PortfolioConflictError("研究组合未归档，无法执行恢复")
                    cursor.execute(
                        """UPDATE research_portfolios
                           SET status = 'active', archived_at = NULL WHERE id = %s""",
                        (portfolio_id,),
                    )
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def archive_portfolio(
        self, username: str, portfolio_id: str, *, expected_version: int
    ) -> dict[str, Any]:
        return self._change_status(
            username,
            portfolio_id,
            expected_version=expected_version,
            target_status="archived",
        )

    def restore_portfolio(
        self, username: str, portfolio_id: str, *, expected_version: int
    ) -> dict[str, Any]:
        return self._change_status(
            username,
            portfolio_id,
            expected_version=expected_version,
            target_status="active",
        )

    @staticmethod
    def _validate_total_weight(holdings: list[dict[str, Any]]) -> None:
        total = sum((row["weight_pct"] for row in holdings), ZERO)
        if total > HUNDRED:
            raise PortfolioValidationError("持仓权重合计不能超过 100%")

    def add_holding(
        self,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int,
        holding: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                cursor.execute(
                    """SELECT id FROM research_portfolio_holdings
                       WHERE portfolio_id = %s AND bond_code = %s""",
                    (portfolio_id, holding["bond_code"]),
                )
                if cursor.fetchone():
                    raise PortfolioConflictError("该债券代码已存在于组合中")
                holdings = self._holding_rows(cursor, portfolio_id)
                self._validate_total_weight([*holdings, holding])
                next_order = max((int(row["sort_order"]) for row in holdings), default=-1) + 1
                cursor.execute(
                    """INSERT INTO research_portfolio_holdings
                         (portfolio_id, bond_code, bond_name, asset_category,
                          weight_pct, yield_pct, duration_years, sort_order, note)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        portfolio_id,
                        *(holding[field] for field in HOLDING_FIELDS[:4]),
                        holding.get("yield_pct"),
                        holding.get("duration_years"),
                        next_order,
                        holding.get("note"),
                    ),
                )
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def update_holding(
        self,
        username: str,
        portfolio_id: str,
        holding_id: int,
        *,
        expected_version: int,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        updates = {key: value for key, value in changes.items() if key in HOLDING_FIELDS}
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                cursor.execute(
                    """SELECT * FROM research_portfolio_holdings
                       WHERE id = %s AND portfolio_id = %s""",
                    (holding_id, portfolio_id),
                )
                current = cursor.fetchone()
                if not current:
                    raise PortfolioNotFoundError("持仓不存在")
                if "bond_code" in updates and updates["bond_code"] != current["bond_code"]:
                    cursor.execute(
                        """SELECT id FROM research_portfolio_holdings
                           WHERE portfolio_id = %s AND bond_code = %s AND id <> %s""",
                        (portfolio_id, updates["bond_code"], holding_id),
                    )
                    if cursor.fetchone():
                        raise PortfolioConflictError("该债券代码已存在于组合中")
                merged = {**current, **updates}
                other_holdings = [
                    row for row in self._holding_rows(cursor, portfolio_id) if row["id"] != holding_id
                ]
                self._validate_total_weight([*other_holdings, merged])
                assignments = ", ".join(f"{field} = %s" for field in updates)
                if updates:
                    cursor.execute(
                        f"""UPDATE research_portfolio_holdings
                            SET {assignments}, updated_at = CURRENT_TIMESTAMP(6)
                            WHERE id = %s AND portfolio_id = %s""",
                        (*updates.values(), holding_id, portfolio_id),
                    )
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def delete_holding(
        self,
        username: str,
        portfolio_id: str,
        holding_id: int,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                affected = cursor.execute(
                    """DELETE FROM research_portfolio_holdings
                       WHERE id = %s AND portfolio_id = %s""",
                    (holding_id, portfolio_id),
                )
                if affected != 1:
                    raise PortfolioNotFoundError("持仓不存在")
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def reorder_holdings(
        self,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int,
        holding_ids: list[int],
    ) -> dict[str, Any]:
        if len(set(holding_ids)) != len(holding_ids):
            raise PortfolioValidationError("holding_ids 不能包含重复持仓")
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                holdings = self._holding_rows(cursor, portfolio_id)
                current_ids = {int(row["id"]) for row in holdings}
                if set(holding_ids) != current_ids:
                    raise PortfolioValidationError("holding_ids 必须恰好包含组合的全部持仓")
                if holding_ids:
                    cursor.executemany(
                        """UPDATE research_portfolio_holdings
                           SET sort_order = %s, updated_at = CURRENT_TIMESTAMP(6)
                           WHERE id = %s AND portfolio_id = %s""",
                        [
                            (sort_order, holding_id, portfolio_id)
                            for sort_order, holding_id in enumerate(holding_ids)
                        ],
                    )
                self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
            conn.commit()
        return self.get_portfolio(username, portfolio_id)

    def import_holdings(
        self,
        username: str,
        portfolio_id: str,
        *,
        expected_version: int,
        mode: Literal["append", "replace"],
        content: bytes,
    ) -> dict[str, Any]:
        """校验并整批导入；任何行错误均回滚且不推进版本。"""
        errors: list[dict[str, Any]] = []
        imported_count = 0
        with self._connection() as conn:
            with conn.cursor() as cursor:
                portfolio = self._lock_portfolio(
                    cursor,
                    username,
                    portfolio_id,
                    expected_version=expected_version,
                )
                try:
                    imported, errors = parse_holdings_csv(content)
                except CsvImportTooLargeError as exc:
                    raise PortfolioImportTooLargeError(str(exc)) from exc
                except CsvImportFormatError as exc:
                    raise PortfolioValidationError(str(exc)) from exc

                existing = self._holding_rows(cursor, portfolio_id)
                if not errors and mode == "append":
                    existing_codes = {str(row["bond_code"]).casefold() for row in existing}
                    for row in imported:
                        if row["bond_code"].casefold() in existing_codes:
                            errors.append(
                                {
                                    "row": row["_row"],
                                    "field": "bond_code",
                                    "message": "债券代码已存在，append 模式不能重复导入",
                                }
                            )
                if not errors:
                    running_total = (
                        sum((row["weight_pct"] for row in existing), ZERO)
                        if mode == "append"
                        else ZERO
                    )
                    for row in imported:
                        running_total += row["weight_pct"]
                        if running_total > HUNDRED:
                            errors.append(
                                {
                                    "row": row["_row"],
                                    "field": "weight_pct",
                                    "message": "导入后持仓权重合计不能超过 100%",
                                }
                            )
                            break

                if errors:
                    conn.rollback()
                elif not imported and mode == "append":
                    # 空 append 是明确的无操作，不制造无意义版本。
                    conn.rollback()
                else:
                    if mode == "replace":
                        cursor.execute(
                            "DELETE FROM research_portfolio_holdings WHERE portfolio_id = %s",
                            (portfolio_id,),
                        )
                    next_order = (
                        max((int(row["sort_order"]) for row in existing), default=-1) + 1
                        if mode == "append"
                        else 0
                    )
                    if imported:
                        cursor.executemany(
                            """INSERT INTO research_portfolio_holdings
                                 (portfolio_id, bond_code, bond_name, asset_category,
                                  weight_pct, yield_pct, duration_years, sort_order, note)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            [
                                (
                                    portfolio_id,
                                    row["bond_code"],
                                    row["bond_name"],
                                    row["asset_category"],
                                    row["weight_pct"],
                                    row["yield_pct"],
                                    row["duration_years"],
                                    next_order + index,
                                    row["note"],
                                )
                                for index, row in enumerate(imported)
                            ],
                        )
                    imported_count = len(imported)
                    self._bump_version(cursor, username, portfolio_id, int(portfolio["version"]))
                    conn.commit()

        return {
            "imported_count": imported_count,
            "errors": errors,
            "portfolio": self.get_portfolio(username, portfolio_id),
        }
