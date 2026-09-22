"""Small HTTP gateway used by the public MCP tools.

The MCP process deliberately calls the existing FastAPI contract instead of
duplicating router/database logic.  This keeps the facade isolated and makes
the first release safe to remove or deploy separately.
"""

from __future__ import annotations

import os
from typing import Any

from backend.agent.client import BackendError, Client, NetworkError


class SentimentBackendGateway:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client = Client(
            base_url=base_url
            or os.environ.get("SENTIMENT_INTERNAL_API_URL", "http://127.0.0.1:8000"),
            token=token or os.environ.get("SENTIMENT_INTERNAL_API_TOKEN"),
            timeout=timeout,
        )

    def get(self, path: str, **query: Any) -> Any:
        """Call one allow-listed JSON GET endpoint and unwrap the API data shell."""
        try:
            _status, payload = self._client.request("GET", path, query=query)
        except BackendError as exc:
            raise RuntimeError(f"Sentiment API returned HTTP {exc.status}") from exc
        except NetworkError as exc:
            raise RuntimeError("Sentiment API is unavailable") from exc

        if isinstance(payload, dict) and set(payload) == {"data"}:
            return payload["data"]
        return payload
