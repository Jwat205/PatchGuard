from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.schemas import AgentFinding, QualityAgentResponse


class QualityAgent(BaseAgent):
    name = "quality"

    def build_prompt(self, context: dict[str, Any]) -> str:
        diff = context.get("diff", "")
        file_context = context.get("file_context", "")
        pr_title = context.get("pr_title", "Untitled PR")
        return f"""You are a senior code reviewer analyzing a GitHub PR diff.

PR Title: {pr_title}

DIFF:
{diff}

FILE CONTEXT (surrounding code):
{file_context}

Analyze for code quality issues only. Return ONLY valid JSON — no markdown fences, no explanation.

Issues to identify:
- Missing test coverage for changed code
- Performance problems (N+1 queries, inefficient loops)
- Poor naming or unclear logic
- Missing error handling
- Code duplication
- Excessive complexity (function too long, too many parameters)

Return this exact JSON structure:
{{
  "findings": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 42,
      "finding_type": "missing_test",
      "severity": "warning",
      "message": "Function changed but no tests added",
      "suggested_fix": "Add test case in test_file.py",
      "is_blocking": false
    }}
  ],
  "summary": "One-sentence overall code quality summary"
}}

Rules:
- Limit findings to max 5
- severity must be one of: info, warning, critical
- message and suggested_fix must be plain English only — NO code snippets, NO quotes from the diff, NO string concatenation expressions
- line_number must be a plain integer (e.g. 42), never null, "N/A", or 0
"""

    def parse_response(self, raw: str, context: dict[str, Any]) -> dict[str, Any]:
        data = self._extract_json(raw)
        validated = QualityAgentResponse(**data)
        return {
            "findings": [AgentFinding(**f.model_dump()) for f in validated.findings],
            "summary": validated.summary,
        }
