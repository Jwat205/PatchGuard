from src.db.redis_client import get_redis
from src.services.cache_service import CacheService
from src.services.github_service import GitHubService


async def get_cache_service() -> CacheService:
    redis = await get_redis()
    return CacheService(redis)


async def get_github_service() -> GitHubService:
    return GitHubService()
