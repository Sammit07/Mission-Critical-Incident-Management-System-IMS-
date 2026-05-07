"""Exponential-backoff retry decorator for async DB operations."""
from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F")


def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "%s attempt %d/%d failed: %s. Retrying in %.2fs",
                            func.__name__, attempt + 1, max_attempts, exc, delay,
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
            logger.error(
                "%s failed after %d attempts: %s", func.__name__, max_attempts, last_exc
            )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
