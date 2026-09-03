import json

from fastapi import APIRouter
from redis.asyncio import Redis

router = APIRouter(prefix="/ping", tags=["ping"])

redis = Redis.from_url("redis://localhost:6379", decode_responses=True)


@router.get("/")
async def cached_ping():
    cached = await redis.get("ping_status")
    if cached:
        return json.loads(cached)

    response = {"status": "ok", "cached": False}
    await redis.set("ping_status", json.dumps(response), ex=5)

    return response
