import json
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.schemas import AgentFinding, SecurityAgentResponse


class SecurityAgent(BaseAgent):
    name = "security"

    def build_prompt(self, context: dict[str, Any]) -> str:
        diff = context.get("diff", "")
        file_context = context.get("file_context", "")
        quality_findings = context.get("quality_findings", [])
        layer1_secrets = context.get("layer1_secrets", [])
        return f"""You are a security-focused code reviewer analyzing a GitHub PR diff.

DIFF:
{diff}

FILE CONTEXT:
{file_context}

QUALITY ISSUES ALREADY FOUND (do NOT duplicate these):
{json.dumps(quality_findings, indent=2)}

SECRETS DETECTED BY REGEX/ENTROPY SCANNER:
{json.dumps(layer1_secrets, indent=2)}

Analyze for SECURITY issues ONLY:
1. JWT/auth implementation flaws
   - Algorithm confusion (accepting 'none' or not validating alg header)
   - Missing expiry check (JWT decoded without verifying exp claim)
   - Weak or hardcoded secrets
   - Missing signature verification
2. Exposed secrets in new code (beyond what the regex scanner already caught)
3. SQL injection, command injection, path traversal
4. Overly permissive CORS (allow_origins=["*"] without authentication)
5. Credentials or tokens in comments

Do NOT flag quality issues — focus ONLY on security.

Return ONLY valid JSON:
{{
  "findings": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 42,
      "finding_type": "jwt_missing_expiry",
      "severity": "critical",
      "message": "JWT decoded without expiry validation",
      "remediation": "Add options={{'verify_exp': True}} to jwt.decode()",
      "is_blocking": true
    }}
  ],
  "layer1_detections": {json.dumps(layer1_secrets)}
}}

CRITICAL = must be fixed, blocks PR merge. WARNING = should be fixed, merge allowed. severity must be one of: info, warning, critical.
"""

    def parse_response(self, raw: str, context: dict[str, Any]) -> dict[str, Any]:
        data = self._extract_json(raw)
        validated = SecurityAgentResponse(**data)
        return {
            "findings": [AgentFinding(**f.model_dump()) for f in validated.findings],
            "layer1_detections": validated.layer1_detections,
        }
