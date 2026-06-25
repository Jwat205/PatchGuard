import asyncio
import time

from celery import Celery
from pydantic import ValidationError

from src.config import settings
from src.models.schemas import CeleryTaskRequest
from src.utils.logging import get_logger

logger = get_logger(__name__)

celery_app = Celery(
    "patchguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    task_max_retries=3,
    task_soft_time_limit=120,
    task_time_limit=150,
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    name="review_pr_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def review_pr_task(
    self,
    repo_id: str,
    pr_number: int,
    head_sha: str,
    diff: str,
) -> dict:
    start = time.time()
    logger.info("review_pr_task started", extra={"repo_id": repo_id, "pr_number": pr_number})

    try:
        request = CeleryTaskRequest(repo_id=repo_id, pr_number=pr_number, diff=diff)
    except ValidationError as exc:
        logger.error("Input validation failed", extra={"error": str(exc)})
        raise self.retry(exc=exc)

    latency_ms = int((time.time() - start) * 1000)
    logger.info("review_pr_task completed", extra={"latency_ms": latency_ms})

    return {
        "status": "completed",
        "findings_count": 0,
        "latency_ms": latency_ms,
    }
