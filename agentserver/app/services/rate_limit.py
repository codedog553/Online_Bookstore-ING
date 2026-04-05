from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        async with self._lock:
            bucket = self._events[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
            bucket.append(now)


class AsyncQpsGate:
    def __init__(self, qps: int) -> None:
        self.qps = max(1, qps)
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait_turn(self) -> None:
        min_interval = 1.0 / self.qps
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_call = time.monotonic()
