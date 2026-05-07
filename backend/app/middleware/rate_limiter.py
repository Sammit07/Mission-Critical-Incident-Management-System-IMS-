"""
Sliding-window rate limiter using Redis sorted sets.

Applied to /api/signals to prevent a single producer from overwhelming
the system under cascading-failure conditions.
"""
from __future__ import annotations

import logging
import time

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..config import settings

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_window: int, window_seconds: int) -> None:
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/signals"):
            return await call_next(request)

        client_ip = (request.client.host if request.client else "unknown")

        try:
            from ..database import get_redis
            redis = get_redis()
            if redis:
                key = f"rate_limit:{client_ip}"
                now = time.time()
                window_start = now - self.window_seconds

                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.window_seconds)
                results = await pipe.execute()

                request_count = results[2]
                if request_count > self.requests_per_window:
                    logger.warning(
                        "Rate limit exceeded for %s: %d req/%ds",
                        client_ip, request_count, self.window_seconds,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "limit": self.requests_per_window,
                            "window_seconds": self.window_seconds,
                            "retry_after_seconds": self.window_seconds,
                        },
                    )
        except HTTPException:
            raise
        except Exception as exc:
            # Fail open — don't block ingestion if Redis is temporarily down
            logger.error("Rate limiter error (failing open): %s", exc)

        return await call_next(request)
