from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_db
from src.db.mongodb import get_mongo_db
from src.db.redis_client import get_redis
from src.models.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    services: dict[str, str] = {}

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception:
        services["postgres"] = "error"

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "error"

    # MongoDB
    try:
        mongo = get_mongo_db()
        await mongo.command("ping")
        services["mongodb"] = "ok"
    except Exception:
        services["mongodb"] = "error"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)
