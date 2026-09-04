"""Simple in-process rate limiting by client IP."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from fastapi import HTTPException, Request, status

from app.config import settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_sec: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - window_sec
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests, try again later",
                    headers={"Retry-After": str(window_sec)},
                )
            q.append(now)


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path in {"/", "/docs", "/openapi.json", "/redoc"} or path.endswith("/health"):
        return await call_next(request)

    ip = client_ip(request)
    if path.startswith("/api/v1/auth/login"):
        limiter.check(f"login:{ip}", limit=settings.rate_limit_login_per_minute, window_sec=60)
    elif path.startswith("/api/v1/"):
        limiter.check(f"api:{ip}", limit=settings.rate_limit_api_per_minute, window_sec=60)

    return await call_next(request)
