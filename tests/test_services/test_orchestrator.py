from unittest.mock import AsyncMock, patch

import pytest

from src.models.schemas import AgentFinding, AgentResult
from src.services.orchestrator import ReviewOrchestrator


def _make_result(name: str, findings: list[AgentFinding] | None = None) -> AgentResult:
    return AgentResult(
        agent_name=name,
        success=True,
        findings=findings or [],
        summary=f"{name} summary",
        latency_ms=300,
        validation_passed=True,
    )


@pytest.mark.asyncio
async def test_orchestrator_runs_all_agents():
    orch = ReviewOrchestrator()
    event = {
        "repo_full_name": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc123",
        "base_sha": "base000",
        "pr_title": "Test PR",
        "event_id": "evt-1",
        "event_type": "opened",
    }

    with (
        patch.object(orch._github, "get_pr_diff", new_callable=AsyncMock, return_value="diff text"),
        patch.object(
            orch._quality, "run", new_callable=AsyncMock, return_value=_make_result("quality")
        ),
        patch.object(
            orch._security, "run", new_callable=AsyncMock, return_value=_make_result("security")
        ),
        patch.object(
            orch._dependency, "run", new_callable=AsyncMock, return_value=_make_result("dependency")
        ),
        patch.object(orch._github, "post_review", new_callable=AsyncMock, return_value={}),
        patch("src.services.orchestrator.record_review_event", new_callable=AsyncMock),
    ):
        result = await orch.run(event, review_id="rev-1")

    assert result["status"] == "success"
    assert "latency_ms" in result
    assert result["quality_findings"] == 0
    assert result["security_findings"] == 0


@pytest.mark.asyncio
async def test_orchestrator_counts_findings():
    orch = ReviewOrchestrator()
    finding = AgentFinding(
        file_path="f.py", line_number=1, finding_type="t", severity="warning", message="m"
    )
    event = {
        "repo_full_name": "owner/repo",
        "pr_number": 2,
        "head_sha": "xyz",
        "base_sha": "base",
        "pr_title": "PR",
        "event_id": "evt-2",
        "event_type": "synchronize",
    }

    with (
        patch.object(orch._github, "get_pr_diff", new_callable=AsyncMock, return_value=""),
        patch.object(
            orch._quality,
            "run",
            new_callable=AsyncMock,
            return_value=_make_result("quality", [finding]),
        ),
        patch.object(
            orch._security,
            "run",
            new_callable=AsyncMock,
            return_value=_make_result("security", [finding, finding]),
        ),
        patch.object(
            orch._dependency, "run", new_callable=AsyncMock, return_value=_make_result("dependency")
        ),
        patch.object(orch._github, "post_review", new_callable=AsyncMock, return_value={}),
        patch("src.services.orchestrator.record_review_event", new_callable=AsyncMock),
    ):
        result = await orch.run(event, review_id="rev-2")

    assert result["quality_findings"] == 1
    assert result["security_findings"] == 2
