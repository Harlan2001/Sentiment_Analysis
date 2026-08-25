from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from backend.config.config import API_PREFIX
from backend.repositories.watchlist_repository import WatchlistRepository
from backend.routers.workbench.helpers import raise_repository_error


router = APIRouter(prefix=f"{API_PREFIX}/watchlist", tags=["watchlist"])


class WatchlistItemCreateRequest(BaseModel):
    object_type: Literal["news", "factor", "macro_signal"]
    object_id: str = Field(min_length=1, max_length=191)
    title: str = Field(min_length=1, max_length=240)
    source_url: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("object_id", "title")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("不能为空")
        return value


def _repository() -> WatchlistRepository:
    return WatchlistRepository.from_environment()


@router.get("")
def list_watchlist(request: Request):
    try:
        return {"data": {"items": _repository().list_items(request.state.username)}}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def add_watchlist_item(request: Request, body: WatchlistItemCreateRequest):
    try:
        item = _repository().add_item(request.state.username, **body.model_dump())
        return {"data": item}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{item_id}")
def remove_watchlist_item(request: Request, item_id: str):
    try:
        return {"data": _repository().remove_item(request.state.username, item_id)}
    except Exception as exc:
        raise_repository_error(exc)
