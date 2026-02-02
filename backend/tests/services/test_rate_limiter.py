"""Tests for RateLimiter — Redis fixed-window rate limiting.

Run: pytest backend/tests/services/test_rate_limiter.py -v --noconftest
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.rate_limiter import RateLimitExceeded, RateLimiter


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_limiter(incr_return=1, redis_fail=False):
    """Build a RateLimiter with a mocked Redis client."""
    redis = AsyncMock()
    if redis_fail:
        redis.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
    else:
        redis.incr = AsyncMock(return_value=incr_return)
    redis.expire = AsyncMock()
    return RateLimiter(redis=redis)


# ── Tests ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_under_limit_passes():
    """Requests under the limit should not raise."""
    limiter = _make_limiter(incr_return=1)
    # Should not raise
    await limiter.check("test_key_hash", limit=100)


@pytest.mark.asyncio
async def test_over_limit_raises_rate_limit_exceeded():
    """Requests over the limit should raise RateLimitExceeded with retry_after."""
    limiter = _make_limiter(incr_return=101)

    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.check("test_key_hash", limit=100)

    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_redis_failure_fails_open():
    """Redis errors should not block requests."""
    limiter = _make_limiter(redis_fail=True)
    # Should not raise despite Redis being down
    await limiter.check("test_key_hash", limit=100)


@pytest.mark.asyncio
async def test_custom_limit_override():
    """Custom limit should be used instead of the default."""
    limiter = _make_limiter(incr_return=6)

    # With custom limit of 5, count=6 should exceed
    with pytest.raises(RateLimitExceeded):
        await limiter.check("test_key_hash", limit=5)

    # With custom limit of 10, count=6 should pass
    limiter2 = _make_limiter(incr_return=6)
    await limiter2.check("test_key_hash", limit=10)


@pytest.mark.asyncio
async def test_first_request_sets_expire():
    """First request in a window (count=1) should set an expiry on the key."""
    limiter = _make_limiter(incr_return=1)
    await limiter.check("test_key_hash", limit=100)
    limiter._redis.expire.assert_called_once()
