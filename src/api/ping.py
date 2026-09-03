import json
import os

from fastapi import APIRouter
from redis.asyncio import Redis

router = APIRouter(prefix="/ping", tags=["ping"])

UPSTASH_URL = os.getenv("UPSTASH_REDIS_URL", "redis://localhost:6379")


async def get_redis():
    return Redis.from_url(UPSTASH_URL, decode_responses=True)


@router.get("/")
async def cached_ping():
    redis = await get_redis()
    cached = await redis.get("ping_status")
    if cached:
        return json.loads(cached)

    response = {"status": "ok", "cached": False}
    await redis.set("ping_status", json.dumps(response), ex=5)

    return response
