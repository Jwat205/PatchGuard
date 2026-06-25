import aiohttp

from src.config import settings
from src.db.redis_client import get_redis
from src.services.cache_service import CacheService
from src.utils.cache_keys import pr_diff_key
from src.utils.logging import get_logger

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"


class GitHubService:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def get_pr_diff(self, repo_full_name: str, pr_number: int, head_sha: str) -> str:
        """Fetch the unified diff for a PR, with Redis caching keyed on head_sha."""
        redis = await get_redis()
        cache = CacheService(redis)
        cache_key = pr_diff_key(repo_full_name, head_sha)

        cached = await cache.get(cache_key)
        if cached:
            logger.info("PR diff cache hit", extra={"repo": repo_full_name, "pr": pr_number})
            return cached

        url = f"{_GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
        async with aiohttp.ClientSession(
            headers={**self._headers, "Accept": "application/vnd.github.v3.diff"}
        ) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                diff = await resp.text()

        await cache.set(cache_key, diff, ttl=settings.redis_ttl_seconds)
        logger.info("PR diff fetched from GitHub", extra={"repo": repo_full_name, "pr": pr_number})
        return diff

    async def get_file_content(self, repo_full_name: str, file_path: str, ref: str) -> str:
        """Fetch raw file content at a specific ref, cached by commit sha."""
        redis = await get_redis()
        cache = CacheService(redis)

        cached = await cache.get_cached_file(repo_full_name, file_path, ref)
        if cached:
            return cached

        url = f"{_GITHUB_API}/repos/{repo_full_name}/contents/{file_path}"
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(url, params={"ref": ref}) as resp:
                resp.raise_for_status()
                data = await resp.json()
                import base64

                content = base64.b64decode(data["content"]).decode("utf-8")

        await cache.set_cached_file(repo_full_name, file_path, ref, content)
        return content

    async def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_id: str,
        findings: list[dict],
        latency_ms: int,
    ) -> dict:
        """Post inline review comments; uses REQUEST_CHANGES if any finding is blocking."""
        comments = []
        blocking_count = 0

        body_findings = []
        for f in findings:
            finding_body = f"**{f.get('finding_type') or 'finding'}** ({f.get('severity', 'info')})\n{f['message']}"
            if f.get("suggested_fix"):
                finding_body += f"\n\n💡 Fix: {f['suggested_fix']}"
            if f.get("remediation"):
                finding_body += f"\n\n🔧 Remediation: {f['remediation']}"
            if f.get("file_path") and f.get("line_number"):
                comments.append(
                    {"path": f["file_path"], "line": f["line_number"], "body": finding_body}
                )
            else:
                body_findings.append(finding_body)
            if f.get("is_blocking"):
                blocking_count += 1

        event = "REQUEST_CHANGES" if blocking_count > 0 else "COMMENT"
        review_body = f"🤖 PatchGuard review — {len(findings)} finding(s) in {latency_ms}ms"
        if body_findings:
            review_body += "\n\n" + "\n\n---\n\n".join(body_findings)

        url = f"{_GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        payload = {
            "commit_id": commit_id,
            "body": review_body,
            "event": event,
            "comments": comments,
        }

        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.post(url, json=payload) as resp:
                status_code = resp.status
                resp_data = await resp.json()

        logger.info(
            "GitHub review posted",
            extra={"repo": repo_full_name, "pr": pr_number, "blocking": blocking_count > 0},
        )
        return {
            "status": "success" if status_code == 201 else "failed",
            "review_id": resp_data.get("id"),
            "comments_posted": len(comments),
            "blocking": blocking_count > 0,
        }
