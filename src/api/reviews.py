import orjson
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import verify_jwt_token
from src.db.database import get_db
from src.db.redis_client import get_redis

router = APIRouter()

CACHE_TTL = 300  # 5 minutes
CACHE_KEY_LIST = "pg:reviews:list:latest50"


@router.get("/reviews")
async def list_reviews(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(verify_jwt_token),
):
    redis = await get_redis()

    cached = await redis.get(CACHE_KEY_LIST)
    if cached:
        return {"success": True, "data": {"reviews": orjson.loads(cached)}}

    stmt = """
    SELECT id, pr_number, repo, summary, created_at
    FROM pr_reviews
    ORDER BY created_at DESC
    LIMIT 50;
    """

    result = await db.execute(stmt)
    rows = [dict(row) for row in result.mappings().all()]

    await redis.set(CACHE_KEY_LIST, orjson.dumps(rows), ex=CACHE_TTL)

    return {"success": True, "data": {"reviews": rows}}


@router.get("/reviews/{review_id}")
async def get_single_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(verify_jwt_token),
):
    redis = await get_redis()
    cache_key = f"pg:review:{review_id}"

    cached = await redis.get(cache_key)
    if cached:
        return orjson.loads(cached)

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

    await redis.set(cache_key, orjson.dumps(payload), ex=CACHE_TTL)

    return payload
