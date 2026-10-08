"""In-memory token bucket rate limiter for general and AI endpoints."""

import time
from typing import Dict, Tuple
from fastapi import Request
from backend.core.config import settings
from backend.core.errors import RateLimitedError


class TokenBucketLimiter:
    def __init__(self):
        # key -> (tokens, last_update_ts)
        self._buckets: Dict[str, Tuple[float, float]] = {}

    def check(self, key: str, capacity: int, refill_rate_per_sec: float) -> None:
        """Check and consume one token. Refill according to elapsed time."""
        now = time.time()
        if key not in self._buckets:
            self._buckets[key] = (float(capacity - 1), now)
            return

        tokens, last_update = self._buckets[key]
        elapsed = now - last_update
        tokens = min(float(capacity), tokens + elapsed * refill_rate_per_sec)

        if tokens < 1.0:
            retry_after = int((1.0 - tokens) / refill_rate_per_sec) + 1
            raise RateLimitedError(retry_after=retry_after)

        self._buckets[key] = (tokens - 1.0, now)

    def check_user(self, user_key: str, is_ai: bool = False) -> None:
        if is_ai:
            capacity = settings.RATE_LIMIT_AI_PER_MIN
            refill_rate = capacity / 60.0
            self.check(f"ai:{user_key}", capacity=capacity, refill_rate_per_sec=refill_rate)
        else:
            capacity = settings.RATE_LIMIT_GENERAL_PER_MIN
            refill_rate = capacity / 60.0
            self.check(f"gen:{user_key}", capacity=capacity, refill_rate_per_sec=refill_rate)


limiter = TokenBucketLimiter()


def rate_limit_ai(request: Request) -> None:
    """Dependency for AI endpoints (10 req/min/user)."""
    user_key = getattr(request.state, "user_id", None) or request.client.host if request.client else "anon"
    limiter.check_user(str(user_key), is_ai=True)


def rate_limit_general(request: Request) -> None:
    """Dependency for standard endpoints (120 req/min/user)."""
    user_key = getattr(request.state, "user_id", None) or request.client.host if request.client else "anon"
    limiter.check_user(str(user_key), is_ai=False)
