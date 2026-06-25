from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    with (
        patch("src.api.health.get_redis", return_value=AsyncMock(ping=AsyncMock())),
        patch("src.api.health.get_mongo_db", return_value=AsyncMock(command=AsyncMock())),
    ):
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "services" in body


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "PatchGuard"
