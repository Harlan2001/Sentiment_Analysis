"""Collect and validate auditable news references from Agent tool results."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlsplit

NewsReference = dict[str, Any]


def _safe_source_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _candidate(value: dict[str, Any]) -> NewsReference | None:
    title = value.get("title")
    raw_id = value.get("news_id", value.get("id"))
    if not isinstance(title, str) or not title.strip() or raw_id is None:
        return None
    try:
        news_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    if news_id <= 0:
        return None
    publish_time = value.get("publish_time", value.get("pub_time"))
    source = value.get("source")
    return {
        "news_id": news_id,
        "title": title.strip()[:500],
        "publish_time": str(publish_time) if publish_time is not None else None,
        "source": str(source).strip()[:200] if source is not None else None,
        "source_url": _safe_source_url(value.get("source_url", value.get("url"))),
    }


def extract_news_references(tool_name: str, result: Any) -> list[NewsReference]:
    """Extract news records only from actual news-tool results."""
    if not tool_name.startswith("news_"):
        return []
    found: list[NewsReference] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            item = _candidate(value)
            if item:
                found.append(item)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)
    return merge_news_references([], found)


def merge_news_references(
    current: Iterable[NewsReference], incoming: Iterable[NewsReference]
) -> list[NewsReference]:
    merged: list[NewsReference] = []
    positions: dict[int, int] = {}
    for item in [*current, *incoming]:
        news_id = int(item["news_id"])
        if news_id in positions:
            existing = merged[positions[news_id]]
            for field in ("title", "publish_time", "source", "source_url"):
                if not existing.get(field) and item.get(field):
                    existing[field] = item[field]
            continue
        positions[news_id] = len(merged)
        merged.append(dict(item))
    return merged


def cited_news_references(
    markdown: str, references: Iterable[NewsReference]
) -> list[NewsReference]:
    """Keep references that the final answer actually identifies.

    A model-created URL is never trusted on its own: it must first match a URL,
    internal news path, or title found in an executed news-tool result.
    """
    selected: list[NewsReference] = []
    for item in references:
        news_id = int(item["news_id"])
        source_url = item.get("source_url")
        mentioned = (
            (isinstance(source_url, str) and source_url in markdown)
            or f"/news/{news_id}" in markdown
            or str(item.get("title") or "") in markdown
        )
        if mentioned:
            normalized = dict(item)
            normalized["index"] = len(selected) + 1
            selected.append(normalized)
    return selected
