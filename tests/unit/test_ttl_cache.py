"""进程内 TTL 缓存单测（S3-3）。"""

from __future__ import annotations

import time

from backend.common.ttl_cache import TTLCache


class TestTTLCache:
    def test_miss_returns_none(self):
        cache: TTLCache[dict] = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_set_then_get(self):
        cache: TTLCache[str] = TTLCache(ttl_seconds=60)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_expiry_evicts_entry(self):
        cache: TTLCache[str] = TTLCache(ttl_seconds=0.02)
        cache.set("k", "v")
        time.sleep(0.03)
        assert cache.get("k") is None

    def test_get_or_set_calls_factory_only_on_miss(self):
        cache: TTLCache[int] = TTLCache(ttl_seconds=60)
        calls = []

        def factory() -> int:
            calls.append(1)
            return 42

        assert cache.get_or_set("k", factory) == 42
        assert cache.get_or_set("k", factory) == 42
        assert len(calls) == 1

    def test_falsy_values_are_valid_cache_entries(self):
        # 空 dict / 空 list / 0 都是合法值，不能被当成未命中导致重复回源
        cache: TTLCache[dict] = TTLCache(ttl_seconds=60)
        calls = []
        assert cache.get_or_set("empty", lambda: (calls.append(1), {})[1]) == {}
        assert cache.get_or_set("empty", lambda: (calls.append(1), {})[1]) == {}
        assert len(calls) == 1

    def test_clear_evicts_all(self):
        cache: TTLCache[int] = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_distinct_keys_independent(self):
        cache: TTLCache[int] = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
