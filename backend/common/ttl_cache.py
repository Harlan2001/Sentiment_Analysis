"""进程内 TTL 缓存（S3-3 排行榜接口用）。

不引新依赖：threading.Lock 保护一个 {key: (expire_at, value)} dict。
适用场景是排行榜这种「可容忍分钟级陈旧、查询成本高」的读接口；
分页新闻流不缓存。空字典/空列表等 falsy 值也是合法缓存值，
内部用哨兵区分「未命中」与「命中了 falsy 值」。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Generic, Optional, TypeVar

_MISSING = object()
T = TypeVar("T")


class TTLCache(Generic[T]):
    """单进程键值 TTL 缓存；monotonic 时钟不受系统时间回拨影响。"""

    def __init__(self, ttl_seconds: float = 120.0) -> None:
        self._ttl = float(ttl_seconds)
        self._lock = threading.Lock()
        self._store: dict[Any, tuple[float, T]] = {}

    def _get_entry(self, key: Any) -> Any:
        """返回哨兵 _MISSING 表示未命中/过期；否则返回原值（允许 falsy 值）。"""
        hit = self._store.get(key, _MISSING)
        if hit is _MISSING:
            return _MISSING
        expires_at, value = hit
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return _MISSING
        return value

    def get(self, key: Any) -> Optional[T]:
        with self._lock:
            entry = self._get_entry(key)
            return None if entry is _MISSING else entry

    def set(self, key: Any, value: T) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def get_or_set(self, key: Any, factory: Callable[[], T]) -> T:
        with self._lock:
            entry = self._get_entry(key)
            if entry is not _MISSING:
                return entry
        # factory 在锁外执行，避免慢查询阻塞其他键的读写
        value = factory()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
