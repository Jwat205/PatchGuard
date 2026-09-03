import uuid
from decimal import Decimal
from typing import Any

from src.config import settings
from src.db.dynamodb import dynamodb_resource
from src.models.dynamodb_models import PREvent, ReviewEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _decimal_to_number(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _decimal_to_number(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decimal_to_number(v) for v in value]
    return value


async def record_pr_event(event: dict[str, Any]) -> None:
    doc = PREvent(
        event_id=event["event_id"],
        event_type=event["event_type"],
        repo_full_name=event["repo_full_name"],
        pr_number=event["pr_number"],
        head_sha=event["head_sha"],
        payload=event,
    )
    async with dynamodb_resource() as resource:
        table = await resource.Table(settings.dynamodb_pr_events_table)
        await table.put_item(Item=doc.to_item())
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
    async with dynamodb_resource() as resource:
        table = await resource.Table(settings.dynamodb_review_events_table)
        await table.put_item(Item=doc.to_item())


async def get_review_events(review_id: str) -> list[dict]:
    async with dynamodb_resource() as resource:
        table = await resource.Table(settings.dynamodb_review_events_table)
        response = await table.query(
            KeyConditionExpression="review_id = :review_id",
            ExpressionAttributeValues={":review_id": review_id},
        )
    return [_decimal_to_number(item) for item in response.get("Items", [])]
