import asyncio
import ssl

from celery import Celery

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

celery_app = Celery(
    "patchguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

_ssl_config = {"ssl_cert_reqs": ssl.CERT_NONE} if settings.redis_url.startswith("rediss://") else {}

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    task_soft_time_limit=120,
    task_time_limit=150,
    worker_prefetch_multiplier=1,
    broker_use_ssl=_ssl_config or None,
    redis_backend_use_ssl=_ssl_config or None,
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
    from src.consumers.handlers import handle_pr_event

    event = {
        "event_id": self.request.id or "",
        "event_type": "synchronize",
        "repo_full_name": repo_id,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": "",
        "pr_title": "",
        "timestamp": "",
    }

    async def _run():
        from src.db.database import engine

        await engine.dispose()
        await handle_pr_event(event)

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error("review_pr_task failed", extra={"error": str(exc)})
        raise self.retry(exc=exc)

    return {"status": "completed", "repo": repo_id, "pr": pr_number}
