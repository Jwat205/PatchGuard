import json
from typing import Any

import redis.asyncio as aioredis

from src.config import settings
from src.services.monitoring import cache_hits, cache_misses
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            cache_misses.inc()
            logger.debug("Cache miss", extra={"key": key})
            return None
        cache_hits.inc()
        logger.debug("Cache hit", extra={"key": key})
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int = settings.redis_ttl_seconds) -> bool:
        serialized = json.dumps(value)
        result = await self._redis.set(key, serialized, ex=ttl)
        return bool(result)

    async def delete(self, key: str) -> int:
        return await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def get_cached_file(self, repo: str, file_path: str, commit_sha: str) -> dict | None:
        from src.utils.cache_keys import github_file_key
        key = github_file_key(repo, file_path, commit_sha)
        return await self.get(key)

    async def set_cached_file(
        self, repo: str, file_path: str, commit_sha: str, content: Any, ttl: int = 3600
    ) -> bool:
        from src.utils.cache_keys import github_file_key
        key = github_file_key(repo, file_path, commit_sha)
        return await self.set(key, content, ttl=ttl)

    async def get_cache_stats(self) -> dict:
        info = await self._redis.info("stats")
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        total = hits + misses
        hit_rate = round((hits / total * 100), 2) if total > 0 else 0.0
        return {"keyspace_hits": hits, "keyspace_misses": misses, "hit_rate": hit_rate}
