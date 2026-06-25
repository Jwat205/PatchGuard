import uuid
from datetime import datetime
from typing import Any

from src.db.database import AsyncSessionLocal
from src.models.postgres_models import Finding, PRReview
from src.services.orchestrator import ReviewOrchestrator
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def handle_pr_event(event: dict[str, Any]) -> None:
    """Dispatch a PR event to the review orchestrator and persist the result."""
    repo_full_name = event["repo_full_name"]
    pr_number = event["pr_number"]
    head_sha = event["head_sha"]

    logger.info("Handling PR event", extra={"repo": repo_full_name, "pr": pr_number})

    async with AsyncSessionLocal() as db:
        review_id = str(uuid.uuid4())
        review = PRReview(
            id=review_id,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha=event.get("base_sha", ""),
            pr_title=event.get("pr_title", ""),
            status="processing",
            created_at=datetime.utcnow(),
        )
        db.add(review)
        await db.commit()

        try:
            orchestrator = ReviewOrchestrator()
            result = await orchestrator.run(event, review_id=review_id)

            review.status = result["status"]
            review.latency_ms = result["latency_ms"]
            review.quality_findings = result["quality_findings"]
            review.security_findings = result["security_findings"]
            review.dependency_findings = result.get("dependency_findings", 0)
            review.agent_results = result.get("agent_results")
            review.updated_at = datetime.utcnow()

            for f in result.get("all_findings", []):
                db.add(Finding(
                    review_id=review_id,
                    agent_type=f.get("agent_type", ""),
                    file_path=f.get("file_path", ""),
                    line_number=f.get("line_number"),
                    finding_type=f.get("finding_type", ""),
                    severity=f.get("severity", "info"),
                    message=f.get("message", ""),
                    suggested_fix=f.get("suggested_fix"),
                    is_blocking=f.get("is_blocking", False),
                ))

            await db.commit()

            logger.info(
                "Review complete",
                extra={"review_id": review_id, "latency_ms": result["latency_ms"]},
            )
        except Exception as exc:
            review.status = "failed"
            review.updated_at = datetime.utcnow()
            await db.commit()
            logger.error("Review failed", extra={"review_id": review_id, "error": str(exc)})
            raise
