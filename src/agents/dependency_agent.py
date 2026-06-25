from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.schemas import AgentFinding, DependencyAgentResponse


class DependencyAgent(BaseAgent):
    name = "dependency"

    def build_prompt(self, context: dict[str, Any]) -> str:
        diff = context.get("diff", "")
        pr_title = context.get("pr_title", "Untitled PR")
        return f"""You are a dependency security reviewer analyzing a GitHub PR diff.

PR Title: {pr_title}

DIFF:
{diff}

Analyze ONLY for dependency-related issues:
1. New packages added with known CVEs or that are deprecated
2. Packages pinned to wildcard versions (e.g. *, >=0.0.0)
3. Dev dependencies used in production code
4. Packages with suspicious names (typosquatting)
5. Major version upgrades that could introduce breaking changes

Return ONLY valid JSON:
{{
  "findings": [
    {{
      "file_path": "requirements.txt",
      "line_number": 5,
      "finding_type": "unpinned_version",
      "severity": "warning",
      "message": "Package 'requests' has no pinned version",
      "suggested_fix": "Pin to requests==2.31.0",
      "is_blocking": false
    }}
  ],
  "summary": "One-sentence summary of dependency health"
}}

Limit findings to max 5. severity must be one of: info, warning, critical.
"""

    def parse_response(self, raw: str, context: dict[str, Any]) -> dict[str, Any]:
        data = self._extract_json(raw)
        validated = DependencyAgentResponse(**data)
        return {
            "findings": [AgentFinding(**f.model_dump()) for f in validated.findings],
            "summary": validated.summary,
        }
