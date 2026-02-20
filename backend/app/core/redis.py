"""Redis async client.

Used for: schema registry cache, WebSocket pub/sub fan-out.
"""

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis.redis_url, decode_responses=True)
    return _redis_client
