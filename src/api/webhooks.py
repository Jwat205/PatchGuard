import json
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from src.consumers.handlers import handle_pr_event
from src.consumers.celery_tasks import review_pr_task
from src.models.schemas import GitHubWebhookPayload, WebhookResponse
from src.services.monitoring import webhook_counter
from src.utils.logging import get_logger
from src.utils.validators import validate_github_signature

logger = get_logger(__name__)
router = APIRouter(prefix="/github", tags=["webhooks"])


@router.post("/webhook", response_model=WebhookResponse)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> WebhookResponse:
    raw_body = await request.body()

    if not validate_github_signature(raw_body, x_hub_signature_256 or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    if x_github_event not in ("pull_request",):
        return WebhookResponse(success=True, message=f"Event '{x_github_event}' ignored")

    try:
        payload_data = json.loads(raw_body)
        payload = GitHubWebhookPayload(**payload_data)
    except Exception as exc:
        logger.warning("Webhook payload validation failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if payload.action not in ("opened", "synchronize", "reopened"):
        return WebhookResponse(success=True, message=f"Action '{payload.action}' ignored")

    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": payload.action,
        "repo_full_name": payload.repo_full_name,
        "pr_number": payload.pr_number,
        "head_sha": payload.head_sha,
        "base_sha": payload.base_sha,
        "pr_title": payload.pr_title,
        "timestamp": datetime.utcnow().isoformat(),
    }

    webhook_counter.inc()

    try:
        review_pr_task.delay(
            repo_id=event["repo_full_name"],
            pr_number=event["pr_number"],
            head_sha=event["head_sha"],
            diff="",
        )
        logger.info("PR event queued via Celery", extra={"event_id": event_id})
    except Exception:
        logger.warning("Celery unavailable — running in-process", extra={"event_id": event_id})
        background_tasks.add_task(handle_pr_event, event)

    return WebhookResponse(success=True, message="Review queued", task_id=event_id)
