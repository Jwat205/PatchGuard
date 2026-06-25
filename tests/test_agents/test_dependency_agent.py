import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.dependency_agent import DependencyAgent
from src.models.schemas import AgentResult

VALID_RESPONSE = json.dumps({
    "findings": [
        {
            "file_path": "requirements.txt",
            "line_number": 3,
            "finding_type": "unpinned_version",
            "severity": "warning",
            "message": "Package has no pinned version",
            "suggested_fix": "Pin to a specific version",
            "is_blocking": False,
        }
    ],
    "summary": "One dependency issue found",
})


def _make_openai_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@pytest.mark.asyncio
async def test_dependency_agent_valid_response():
    agent = DependencyAgent()
    mock = AsyncMock(return_value=_make_openai_response(VALID_RESPONSE))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "requirements diff", "file_context": "", "pr_title": "Bump deps"})

    assert isinstance(result, AgentResult)
    assert result.validation_passed is True
    assert len(result.findings) == 1


@pytest.mark.asyncio
async def test_dependency_agent_invalid_json_does_not_crash():
    agent = DependencyAgent()
    mock = AsyncMock(return_value=_make_openai_response("not json"))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "code", "file_context": "", "pr_title": "Test"})
    assert result.validation_passed is False
