"""Redis fixed-window rate limiter for embed endpoints.

Key: flowforge:ratelimit:<key_hash>:<window_timestamp>

Fails open on Redis errors — a Redis outage should not block embed requests.
"""

import logging
import time

from redis.asyncio import Redis

from app.core.config import settings
from app.core.metrics import rate_limit_checks_total

logger = logging.getLogger(__name__)

RATE_LIMIT_KEY_PREFIX = "flowforge:ratelimit:"


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded. Contains retry_after in seconds."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class RateLimiter:
    """Redis fixed-window rate limiter."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def check(self, key_hash: str, limit: int | None = None) -> None:
        """Check rate limit for the given key hash.

        Args:
            key_hash: The SHA-256 hash of the API key.
            limit: Override limit. If None, uses settings.embed_rate_limit_default.

        Raises:
            RateLimitExceeded: If the rate limit is exceeded.
        """
        effective_limit = limit if limit is not None else settings.embed_rate_limit_default
        window = settings.embed_rate_limit_window

        window_ts = int(time.time() // window)
        redis_key = f"{RATE_LIMIT_KEY_PREFIX}{key_hash}:{window_ts}"

        try:
            count = await self._redis.incr(redis_key)
            if count == 1:
                # First request in this window — set expiry
                await self._redis.expire(redis_key, window + 1)

            if count > effective_limit:
                rate_limit_checks_total.labels(status="rejected").inc()
                # Time remaining in the current window
                retry_after = round(window - (time.time() % window), 1)
                if retry_after <= 0:
                    retry_after = 0.1
                raise RateLimitExceeded(retry_after=retry_after)

            rate_limit_checks_total.labels(status="allowed").inc()
        except RateLimitExceeded:
            raise
        except Exception:
            # Fail open — Redis errors should not block requests
            rate_limit_checks_total.labels(status="error").inc()
            logger.warning(
                "Rate limiter Redis error for key %s, failing open",
                key_hash,
                exc_info=True,
            )
