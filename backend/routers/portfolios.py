"""账号级研究组合 API。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.common.api_response import ok
from backend.common.pagination import page_param, page_size_param, paginated_payload
from backend.config.config import API_PREFIX
from backend.portfolio.csv_io import BOND_CODE_PATTERN, MAX_IMPORT_BYTES, build_portfolio_csv
from backend.repositories.portfolio_repository import PortfolioRepository
from backend.routers.workbench_helpers import raise_repository_error

router = APIRouter(prefix=f"{API_PREFIX}/portfolios", tags=["portfolios"])


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("字段不能为空或仅包含空白")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _bond_code(value: str) -> str:
    value = _required_text(value)
    if BOND_CODE_PATTERN.fullmatch(value) is None:
        raise ValueError("债券代码仅支持 ASCII 字母、数字、点、下划线和连字符，长度为 1-32")
    return value


class PortfolioCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    size_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    as_of_date: date
    target_duration: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=4
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _optional_text(value)


class PortfolioPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    size_amount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    as_of_date: date | None = None
    target_duration: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=4
    )
    expected_version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_patch(self):
        for field in ("name", "size_amount", "as_of_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        if not self.model_fields_set.difference({"expected_version"}):
            raise ValueError("至少提供一个待修改字段")
        return self


class PortfolioCopyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None


class VersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class HoldingCreateRequest(BaseModel):
    bond_code: str = Field(min_length=1, max_length=32)
    bond_name: str = Field(min_length=1, max_length=120)
    asset_category: str = Field(min_length=1, max_length=40)
    weight_pct: Decimal = Field(gt=0, le=100, max_digits=9, decimal_places=6)
    yield_pct: Decimal | None = Field(default=None, max_digits=10, decimal_places=6)
    duration_years: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=4
    )
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)

    @field_validator("bond_code")
    @classmethod
    def clean_bond_code(cls, value: str) -> str:
        return _bond_code(value)

    @field_validator("bond_name", "asset_category")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _optional_text(value)


class HoldingPatchRequest(BaseModel):
    bond_code: str | None = Field(default=None, min_length=1, max_length=32)
    bond_name: str | None = Field(default=None, min_length=1, max_length=120)
    asset_category: str | None = Field(default=None, min_length=1, max_length=40)
    weight_pct: Decimal | None = Field(
        default=None, gt=0, le=100, max_digits=9, decimal_places=6
    )
    yield_pct: Decimal | None = Field(default=None, max_digits=10, decimal_places=6)
    duration_years: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=4
    )
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)

    @field_validator("bond_code")
    @classmethod
    def clean_bond_code(cls, value: str | None) -> str | None:
        return _bond_code(value) if value is not None else None

    @field_validator("bond_name", "asset_category")
    @classmethod
    def clean_required(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_patch(self):
        for field in ("bond_code", "bond_name", "asset_category", "weight_pct"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        if not self.model_fields_set.difference({"expected_version"}):
            raise ValueError("至少提供一个待修改字段")
        return self


class HoldingOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)
    holding_ids: list[int] = Field(max_length=1000)

    @field_validator("holding_ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if any(holding_id <= 0 for holding_id in value):
            raise ValueError("holding_ids 必须全部为正整数")
        return value


def _repository() -> PortfolioRepository:
    return PortfolioRepository.from_environment()


@router.get("")
def list_portfolios(
    request: Request,
    include_archived: bool = Query(False),
    page: int = page_param(),
    page_size: int = page_size_param(),
):
    try:
        result = _repository().list_portfolios(
            request.state.username,
            include_archived=include_archived,
            page=page,
            page_size=page_size,
        )
        return ok(paginated_payload(result["items"], result["total"], page, page_size))
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def create_portfolio(request: Request, body: PortfolioCreateRequest):
    try:
        return ok(
            _repository().create_portfolio(
                request.state.username,
                **body.model_dump(),
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{portfolio_id}/export")
def export_portfolio(request: Request, portfolio_id: str):
    try:
        detail = _repository().get_portfolio(request.state.username, portfolio_id)
        content = build_portfolio_csv(detail)
        display_name = "".join(
            "_" if ord(character) < 32 or character in '/\\:*?"<>|' else character
            for character in f"{detail['name']}_{detail['id']}.csv"
        ).strip(" .")
        display_name = display_name[:160] or "research-portfolio.csv"
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    "attachment; filename=\"research-portfolio.csv\"; "
                    f"filename*=UTF-8''{quote(display_name, safe='')}"
                ),
                "Cache-Control": "no-store",
            },
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{portfolio_id}")
def get_portfolio(request: Request, portfolio_id: str):
    try:
        return ok(_repository().get_portfolio(request.state.username, portfolio_id))
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{portfolio_id}")
def update_portfolio(request: Request, portfolio_id: str, body: PortfolioPatchRequest):
    try:
        changes = body.model_dump(exclude_unset=True)
        expected_version = changes.pop("expected_version")
        return ok(
            _repository().update_portfolio(
                request.state.username,
                portfolio_id,
                expected_version=expected_version,
                changes=changes,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{portfolio_id}/copy", status_code=201)
def copy_portfolio(request: Request, portfolio_id: str, body: PortfolioCopyRequest):
    try:
        return ok(
            _repository().copy_portfolio(
                request.state.username,
                portfolio_id,
                name=body.name,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{portfolio_id}/archive")
def archive_portfolio(request: Request, portfolio_id: str, body: VersionRequest):
    try:
        return ok(
            _repository().archive_portfolio(
                request.state.username,
                portfolio_id,
                expected_version=body.expected_version,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{portfolio_id}/restore")
def restore_portfolio(request: Request, portfolio_id: str, body: VersionRequest):
    try:
        return ok(
            _repository().restore_portfolio(
                request.state.username,
                portfolio_id,
                expected_version=body.expected_version,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{portfolio_id}/holdings", status_code=201)
def add_holding(request: Request, portfolio_id: str, body: HoldingCreateRequest):
    try:
        holding = body.model_dump()
        expected_version = holding.pop("expected_version")
        return ok(
            _repository().add_holding(
                request.state.username,
                portfolio_id,
                expected_version=expected_version,
                holding=holding,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


# 必须声明在 /holdings/{holding_id} 前，避免 import 被当成动态持仓 ID。
@router.post("/{portfolio_id}/holdings/import")
async def import_holdings(
    request: Request,
    portfolio_id: str,
    mode: Literal["append", "replace"] = Query("append"),
    expected_version: int = Query(ge=1),
    file: UploadFile = File(...),
):
    try:
        content = await file.read(MAX_IMPORT_BYTES + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="文件读取失败") from exc
    finally:
        await file.close()
    try:
        result = _repository().import_holdings(
            request.state.username,
            portfolio_id,
            expected_version=expected_version,
            mode=mode,
            content=content,
        )
        return ok(result)
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{portfolio_id}/holdings/{holding_id}")
def update_holding(
    request: Request,
    portfolio_id: str,
    holding_id: int,
    body: HoldingPatchRequest,
):
    try:
        changes = body.model_dump(exclude_unset=True)
        expected_version = changes.pop("expected_version")
        return ok(
            _repository().update_holding(
                request.state.username,
                portfolio_id,
                holding_id,
                expected_version=expected_version,
                changes=changes,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{portfolio_id}/holdings/{holding_id}")
def delete_holding(
    request: Request,
    portfolio_id: str,
    holding_id: int,
    expected_version: int = Query(ge=1),
):
    try:
        return ok(
            _repository().delete_holding(
                request.state.username,
                portfolio_id,
                holding_id,
                expected_version=expected_version,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.put("/{portfolio_id}/holdings/order")
def reorder_holdings(request: Request, portfolio_id: str, body: HoldingOrderRequest):
    try:
        return ok(
            _repository().reorder_holdings(
                request.state.username,
                portfolio_id,
                expected_version=body.expected_version,
                holding_ids=body.holding_ids,
            )
        )
    except Exception as exc:
        raise_repository_error(exc)
