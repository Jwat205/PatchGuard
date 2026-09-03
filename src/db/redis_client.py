import redis.asyncio as aioredis

from src.config import settings

# Create ONE global Redis client at import time
redis = aioredis.from_url(
    settings.redis_url,
    db=settings.redis_db,
    decode_responses=True,
    encoding="utf-8",
)


async def get_redis():
    return redis


async def close_redis():
    await redis.aclose()
