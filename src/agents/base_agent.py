import json
import time
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from src.config import settings
from src.models.schemas import AgentResult
from src.utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a code review agent. Respond ONLY with a valid JSON object. "
    "No markdown fences, no commentary outside the JSON."
)


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )

    @abstractmethod
    def build_prompt(self, context: dict[str, Any]) -> str: ...

    @abstractmethod
    def parse_response(self, raw: str, context: dict[str, Any]) -> dict[str, Any]: ...

    async def run(self, context: dict[str, Any]) -> AgentResult:
        start = time.time()
        prompt = self.build_prompt(context)
        validation_passed = True

        try:
            completion = await self._client.chat.completions.create(
                model=settings.llm_model,
                max_tokens=1500,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = completion.choices[0].message.content or ""
            validated = self.parse_response(raw, context)
            findings = validated.get("findings", [])
            summary = validated.get("summary", "")
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            logger.error(f"{self.name} validation failed", extra={"error": str(exc)})
            validation_passed = False
            findings = []
            summary = f"{self.name} failed to produce a valid response"
        except Exception as exc:
            logger.error(f"{self.name} agent error", extra={"error": str(exc)})
            validation_passed = False
            findings = []
            summary = f"{self.name} encountered an error"

        latency_ms = int((time.time() - start) * 1000)
        return AgentResult(
            agent_name=self.name,
            success=validation_passed,
            findings=findings,
            summary=summary,
            latency_ms=latency_ms,
            validation_passed=validation_passed,
        )

    def _extract_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
        return json.loads(text)
