import asyncio

import fakeredis.aioredis
import pytest
import pytest_asyncio

from src.services.cache_service import CacheService


@pytest_asyncio.fixture
async def cache():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return CacheService(redis)


@pytest.mark.asyncio
async def test_set_and_get(cache: CacheService):
    await cache.set("key1", {"data": "hello"})
    result = await cache.get("key1")
    assert result == {"data": "hello"}


@pytest.mark.asyncio
async def test_cache_miss_returns_none(cache: CacheService):
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cache_expiration(cache: CacheService):
    await cache.set("expiring", "value", ttl=1)
    assert await cache.get("expiring") == "value"
    await asyncio.sleep(1.1)
    assert await cache.get("expiring") is None


@pytest.mark.asyncio
async def test_delete(cache: CacheService):
    await cache.set("to_delete", 42)
    await cache.delete("to_delete")
    assert await cache.get("to_delete") is None


@pytest.mark.asyncio
async def test_exists(cache: CacheService):
    await cache.set("exists_key", True)
    assert await cache.exists("exists_key") is True
    assert await cache.exists("missing") is False


@pytest.mark.asyncio
async def test_different_commits_separate_cache(cache: CacheService):
    await cache.set_cached_file("repo", "main.py", "commit1", "v1_content")
    await cache.set_cached_file("repo", "main.py", "commit2", "v2_content")
    assert await cache.get_cached_file("repo", "main.py", "commit1") == "v1_content"
    assert await cache.get_cached_file("repo", "main.py", "commit2") == "v2_content"


@pytest.mark.asyncio
async def test_synthetic_load(cache: CacheService):
    await cache.set_cached_file("repo", "hot.py", "sha999", "content")
    hits = 0
    for _ in range(20):
        val = await cache.get_cached_file("repo", "hot.py", "sha999")
        if val is not None:
            hits += 1
    assert hits == 20
