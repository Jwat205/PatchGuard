import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.security_agent import SecurityAgent
from src.models.schemas import AgentResult


def _make_openai_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


JWT_ALGO_CONFUSION = json.dumps({
    "findings": [
        {
            "file_path": "auth.py",
            "line_number": 6,
            "finding_type": "jwt_algorithm_confusion",
            "severity": "critical",
            "message": "JWT decoded with algorithms=['none']",
            "remediation": "Remove 'none' from allowed algorithms",
            "is_blocking": True,
        }
    ],
    "layer1_detections": [],
})

JWT_MISSING_EXPIRY = json.dumps({
    "findings": [
        {
            "file_path": "auth.py",
            "line_number": 10,
            "finding_type": "jwt_missing_expiry",
            "severity": "critical",
            "message": "JWT decoded without expiry check",
            "remediation": "Pass options={'verify_exp': True}",
            "is_blocking": True,
        }
    ],
    "layer1_detections": [],
})


@pytest.mark.asyncio
async def test_detects_jwt_algorithm_confusion():
    agent = SecurityAgent()
    diff = "jwt.decode(token, key, algorithms=['none'])"
    mock = AsyncMock(return_value=_make_openai_response(JWT_ALGO_CONFUSION))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": diff, "file_context": "", "quality_findings": [], "layer1_secrets": []})

    assert result.validation_passed
    assert any(f.finding_type == "jwt_algorithm_confusion" for f in result.findings)
    assert any(f.severity == "critical" for f in result.findings)


@pytest.mark.asyncio
async def test_detects_missing_expiry():
    agent = SecurityAgent()
    diff = "jwt.decode(token, key)"
    mock = AsyncMock(return_value=_make_openai_response(JWT_MISSING_EXPIRY))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": diff, "file_context": "", "quality_findings": [], "layer1_secrets": []})

    assert result.validation_passed
    assert any(f.finding_type == "jwt_missing_expiry" for f in result.findings)


@pytest.mark.asyncio
async def test_validation_pass_rate_across_samples():
    agent = SecurityAgent()
    responses = [JWT_ALGO_CONFUSION, JWT_MISSING_EXPIRY]
    passed = 0
    for resp_json in responses:
        mock = AsyncMock(return_value=_make_openai_response(resp_json))
        with patch.object(agent._client.chat.completions, "create", mock):
            result = await agent.run({"diff": "code", "file_context": "", "quality_findings": [], "layer1_secrets": []})
        if result.validation_passed:
            passed += 1
    assert passed == len(responses), f"Expected 100% pass rate, got {passed}/{len(responses)}"


@pytest.mark.asyncio
async def test_invalid_response_does_not_crash():
    agent = SecurityAgent()
    mock = AsyncMock(return_value=_make_openai_response("not json"))
    with patch.object(agent._client.chat.completions, "create", mock):
        result = await agent.run({"diff": "code", "file_context": "", "quality_findings": [], "layer1_secrets": []})
    assert isinstance(result, AgentResult)
    assert result.validation_passed is False
