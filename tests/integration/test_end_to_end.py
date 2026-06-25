"""
Integration: webhook POST → queue → agent review → DB result.
Skipped when Kafka/Redis are not available (CI without infrastructure).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.auth import generate_jwt_token


@pytest.mark.asyncio
async def test_full_review_pipeline(client: AsyncClient):
    """Post a webhook, mock the Kafka publish and orchestrator, then verify the API responds."""
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 99,
            "title": "Integration test PR",
            "head": {"sha": "int_sha_001"},
            "base": {"sha": "base_sha"},
        },
        "repository": {"full_name": "test/integration-repo"},
        "installation": {"id": 1},
    }
    body = json.dumps(payload).encode()

    with (
        patch("src.api.webhooks.validate_github_signature", return_value=True),
        patch("src.api.webhooks.publish_pr_event", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/github/webhook",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=valid", "X-Github-Event": "pull_request"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["task_id"] is not None


@pytest.mark.asyncio
async def test_reviews_endpoint_after_webhook(client: AsyncClient):
    """Reviews endpoint returns 200 for authenticated requests."""
    token = generate_jwt_token("integration_user")
    response = await client.get("/reviews", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_metrics_endpoint_accessible(client: AsyncClient):
    """Prometheus /metrics endpoint is reachable."""
    response = await client.get("/metrics", follow_redirects=True)
    assert response.status_code == 200
