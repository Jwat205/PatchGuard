from fastapi import APIRouter
from redis.asyncio import Redis
import json
import os

router = APIRouter()

UPSTASH_URL = os.getenv("UPSTASH_REDIS_URL")

async def get_redis():
    return Redis.from_url(UPSTASH_URL, decode_responses=True)

@router.get("/ping")
async def ping():
    redis = await get_redis()

    cached = await redis.get("ping_status")
    if cached:
        return json.loads(cached)

    response = {"status": "ok"}

    await redis.set("ping_status", json.dumps(response), ex=5)

    return response
