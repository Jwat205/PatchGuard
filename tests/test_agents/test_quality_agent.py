import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.quality_agent import QualityAgent
from src.models.schemas import AgentResult


def _make_openai_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


VALID_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "file_path": "app.py",
                "line_number": 15,
                "finding_type": "missing_test",
                "severity": "warning",
                "message": "New function has no tests",
                "suggested_fix": "Add pytest test",
                "is_blocking": False,
            }
        ],
        "summary": "One quality issue found",
    }
)

INVALID_RESPONSE = "This is not JSON at all"


@pytest.mark.asyncio
async def test_quality_agent_valid_response():
    agent = QualityAgent()
    mock = AsyncMock(return_value=_make_openai_response(VALID_RESPONSE))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run(
            {"diff": "def foo(): pass", "file_context": "", "pr_title": "Test"}
        )

    assert isinstance(result, AgentResult)
    assert result.validation_passed is True
    assert len(result.findings) == 1
    assert result.findings[0].finding_type == "missing_test"


@pytest.mark.asyncio
async def test_quality_agent_invalid_response_does_not_crash():
    agent = QualityAgent()
    mock = AsyncMock(return_value=_make_openai_response(INVALID_RESPONSE))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "code", "file_context": "", "pr_title": "Test"})

    assert isinstance(result, AgentResult)
    assert result.validation_passed is False
    assert result.findings == []


@pytest.mark.asyncio
async def test_quality_agent_returns_latency():
    agent = QualityAgent()
    mock = AsyncMock(return_value=_make_openai_response(VALID_RESPONSE))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "code", "file_context": "", "pr_title": "Test"})
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_quality_agent_all_fields_present():
    agent = QualityAgent()
    mock = AsyncMock(return_value=_make_openai_response(VALID_RESPONSE))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "code", "file_context": "", "pr_title": "Test"})
    f = result.findings[0]
    assert f.file_path
    assert f.line_number > 0
    assert f.finding_type
    assert f.severity in ("info", "warning", "critical")
    assert f.message
