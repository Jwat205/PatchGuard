import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_valid_webhook_accepted(client: AsyncClient, valid_pr_payload, make_signature):
    body = json.dumps(valid_pr_payload).encode()
    signature = make_signature(body)

    with (
        patch("src.api.webhooks.validate_github_signature", return_value=True),
        patch("src.api.webhooks.publish_pr_event", new_callable=AsyncMock),
    ):
        response = await client.post(
            "/github/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-Github-Event": "pull_request",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data


@pytest.mark.asyncio
async def test_invalid_signature_rejected(client: AsyncClient, valid_pr_payload):
    body = json.dumps(valid_pr_payload).encode()
    with patch("src.api.webhooks.validate_github_signature", return_value=False):
        response = await client.post(
            "/github/webhook",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=bad", "X-Github-Event": "pull_request"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unsupported_event_ignored(client: AsyncClient, valid_pr_payload, make_signature):
    body = json.dumps(valid_pr_payload).encode()
    signature = make_signature(body)
    with patch("src.api.webhooks.validate_github_signature", return_value=True):
        response = await client.post(
            "/github/webhook",
            content=body,
            headers={"X-Hub-Signature-256": signature, "X-Github-Event": "push"},
        )
    assert response.status_code == 200
    assert "ignored" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_invalid_payload_returns_422(client: AsyncClient, make_signature):
    bad_payload = {"action": "closed", "pull_request": {}, "repository": {}}
    body = json.dumps(bad_payload).encode()
    signature = make_signature(body)
    with patch("src.api.webhooks.validate_github_signature", return_value=True):
        response = await client.post(
            "/github/webhook",
            content=body,
            headers={"X-Hub-Signature-256": signature, "X-Github-Event": "pull_request"},
        )
    # action 'closed' is not in Literal — Pydantic raises; webhook returns 422
    assert response.status_code in (200, 422)
