from unittest.mock import patch

import pytest
from httpx import AsyncClient

from src.auth import generate_jwt_token


def auth_headers() -> dict:
    token = generate_jwt_token("testuser")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_reviews_authenticated(client: AsyncClient):
    response = await client.get("/reviews", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "reviews" in data["data"]


@pytest.mark.asyncio
async def test_list_reviews_unauthenticated(client: AsyncClient):
    response = await client.get("/reviews")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_review_404(client: AsyncClient):
    response = await client.get("/reviews/nonexistent-id", headers=auth_headers())
    assert response.status_code == 404
