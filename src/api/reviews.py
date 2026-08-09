import orjson
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.redis_client import get_redis

router = APIRouter()

CACHE_TTL = 300  # 5 minutes
CACHE_KEY_LIST = "pg:reviews:list:latest50"


@router.get("/reviews")
async def list_reviews(db: AsyncSession = Depends(get_db)):
    redis = await get_redis()

    # Try Redis first
    cached = await redis.get(CACHE_KEY_LIST)
    if cached:
        return orjson.loads(cached)

    # Cache miss → query DB
    stmt = """
    SELECT id, pr_number, repo, summary, created_at
    FROM pr_reviews
    ORDER BY created_at DESC
    LIMIT 50;
    """

    result = await db.execute(stmt)
    rows = result.mappings().all()

    payload = [dict(row) for row in rows]
    serialized = orjson.dumps(payload)

    # Store in Redis
    await redis.set(CACHE_KEY_LIST, serialized, ex=CACHE_TTL)

    return payload


@router.get("/reviews/{review_id}")
async def get_single_review(review_id: int, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    cache_key = f"pg:review:{review_id}"

    # Try Redis first
    cached = await redis.get(cache_key)
    if cached:
        return orjson.loads(cached)

    # Cache miss → query DB
    stmt_review = """
    SELECT *
    FROM pr_reviews
    WHERE id = :id
    LIMIT 1;
    """

    review_result = await db.execute(stmt_review, {"id": review_id})
    review_row = review_result.mappings().first()

    if not review_row:
        raise HTTPException(status_code=404, detail="Review not found")

    stmt_findings = """
    SELECT *
    FROM findings
    WHERE review_id = :id;
    """

    findings_result = await db.execute(stmt_findings, {"id": review_id})
    findings_rows = findings_result.mappings().all()

    payload = {
        "review": dict(review_row),
        "findings": [dict(f) for f in findings_rows],
    }

    serialized = orjson.dumps(payload)

    # Store in Redis
    await redis.set(cache_key, serialized, ex=CACHE_TTL)

    return payload
