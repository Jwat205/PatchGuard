from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.services.github_service import GitHubService


@pytest.fixture
def github_service():
    return GitHubService()


@pytest.mark.asyncio
async def test_get_pr_diff_fetches_from_github(github_service: GitHubService):
    mock_resp = AsyncMock()
    mock_resp.text = AsyncMock(return_value="diff --git a/file.py b/file.py")
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("src.services.github_service.get_redis", return_value=AsyncMock()),
        patch("src.services.github_service.CacheService") as MockCache,
    ):
        mock_cache = MockCache.return_value
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        with patch("aiohttp.ClientSession") as MockSession:
            MockSession.return_value.__aenter__ = AsyncMock(return_value=MockSession.return_value)
            MockSession.return_value.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            MockSession.return_value.get.return_value.__aexit__ = AsyncMock(return_value=False)

            diff = await github_service.get_pr_diff("owner/repo", 1, "abc123")

    assert "diff" in diff


@pytest.mark.asyncio
async def test_post_review_returns_result(github_service: GitHubService):
    mock_resp = AsyncMock()
    mock_resp.status = 201
    mock_resp.json = AsyncMock(return_value={"id": 12345})

    findings = [
        {
            "file_path": "auth.py",
            "line_number": 5,
            "finding_type": "jwt_weak_secret",
            "severity": "critical",
            "message": "Hardcoded secret",
            "is_blocking": True,
        }
    ]

    with patch("aiohttp.ClientSession") as MockSession:
        MockSession.return_value.__aenter__ = AsyncMock(return_value=MockSession.return_value)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        MockSession.return_value.post.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await github_service.post_review("owner/repo", 1, "abc123", findings, 1200)

    assert result["status"] == "success"
    assert result["blocking"] is True
    assert result["comments_posted"] == 1
