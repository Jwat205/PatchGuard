import time
import uuid
from typing import Any

from src.agents.dependency_agent import DependencyAgent
from src.agents.quality_agent import QualityAgent
from src.agents.security_agent import SecurityAgent
from src.models.postgres_models import Finding
from src.services.event_store import record_review_event
from src.services.github_service import GitHubService
from src.services.monitoring import (
    latency_histogram,
    validation_counter,
    validation_failure_counter,
)
from src.services.secret_scanner import scan_for_secrets
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewOrchestrator:
    def __init__(self) -> None:
        self._quality = QualityAgent()
        self._security = SecurityAgent()
        self._dependency = DependencyAgent()
        self._github = GitHubService()

    async def run(self, event: dict[str, Any], review_id: str) -> dict[str, Any]:
        start = time.time()
        repo = event["repo_full_name"]
        pr_number = event["pr_number"]
        head_sha = event["head_sha"]
        pr_title = event.get("pr_title", "")

        diff = await self._github.get_pr_diff(repo, pr_number, head_sha)
        layer1_secrets = scan_for_secrets(diff)

        context = {
            "diff": diff,
            "file_context": "",
            "pr_title": pr_title,
            "layer1_secrets": layer1_secrets,
        }

        quality_result = await self._quality.run(context)
        context["quality_findings"] = [f.model_dump() for f in quality_result.findings]

        security_result = await self._security.run(context)
        dependency_result = await self._dependency.run(context)

        for result in (quality_result, security_result, dependency_result):
            if result.validation_passed:
                validation_counter.inc()
            else:
                validation_failure_counter.inc()

        all_findings: list[dict] = []
        for result in (quality_result, security_result, dependency_result):
            for f in result.findings:
                all_findings.append({**f.model_dump(), "agent_type": result.agent_name})

        latency_ms = int((time.time() - start) * 1000)
        latency_histogram.observe(latency_ms / 1000)

        try:
            await self._github.post_review(repo, pr_number, head_sha, all_findings, latency_ms)
        except Exception as exc:
            logger.warning("Failed to post GitHub review", extra={"error": str(exc)})

        for result in (quality_result, security_result, dependency_result):
            await record_review_event(
                review_id=review_id,
                repo_full_name=repo,
                pr_number=pr_number,
                head_sha=head_sha,
                agent_name=result.agent_name,
                findings_count=len(result.findings),
                validation_passed=result.validation_passed,
                latency_ms=result.latency_ms,
            )

        return {
            "status": "success",
            "latency_ms": latency_ms,
            "quality_findings": len(quality_result.findings),
            "security_findings": len(security_result.findings),
            "dependency_findings": len(dependency_result.findings),
            "all_findings": all_findings,
            "agent_results": {
                "quality": quality_result.model_dump(),
                "security": security_result.model_dump(),
                "dependency": dependency_result.model_dump(),
            },
        }
