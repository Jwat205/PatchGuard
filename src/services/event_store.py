from typing import Any

from src.db.mongodb import get_mongo_db
from src.models.mongodb_models import PREvent, ReviewEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def record_pr_event(event: dict[str, Any]) -> None:
    db = get_mongo_db()
    doc = PREvent(
        event_id=event["event_id"],
        event_type=event["event_type"],
        repo_full_name=event["repo_full_name"],
        pr_number=event["pr_number"],
        head_sha=event["head_sha"],
        payload=event,
    )
    await db["pr_events"].insert_one(doc.model_dump())
    logger.info("PR event recorded", extra={"event_id": event["event_id"]})


async def record_review_event(
    review_id: str,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    agent_name: str,
    findings_count: int,
    validation_passed: bool,
    latency_ms: int,
) -> None:
    import uuid
    db = get_mongo_db()
    doc = ReviewEvent(
        event_id=str(uuid.uuid4()),
        review_id=review_id,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        agent_name=agent_name,
        findings_count=findings_count,
        validation_passed=validation_passed,
        latency_ms=latency_ms,
    )
    await db["review_events"].insert_one(doc.model_dump())


async def get_review_events(review_id: str) -> list[dict]:
    db = get_mongo_db()
    cursor = db["review_events"].find({"review_id": review_id})
    return [doc async for doc in cursor]
