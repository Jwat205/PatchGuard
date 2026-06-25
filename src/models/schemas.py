from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GitHubWebhookPayload(BaseModel):
    action: Literal["opened", "synchronize", "reopened"]
    pull_request: dict[str, Any]
    repository: dict[str, Any]
    installation: dict[str, Any] | None = None

    @property
    def pr_number(self) -> int:
        return self.pull_request["number"]

    @property
    def repo_full_name(self) -> str:
        return self.repository["full_name"]

    @property
    def head_sha(self) -> str:
        return self.pull_request["head"]["sha"]

    @property
    def base_sha(self) -> str:
        return self.pull_request["base"]["sha"]

    @property
    def pr_title(self) -> str:
        return self.pull_request["title"]


class ReviewRequest(BaseModel):
    repo_id: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    pr_title: str
    diff: str


class CeleryTaskRequest(BaseModel):
    repo_id: str
    pr_number: int
    diff: str


class AgentFinding(BaseModel):
    file_path: str | None = None
    line_number: int | None = None
    finding_type: str | None = None
    severity: Literal["info", "warning", "critical"] = "info"
    message: str
    suggested_fix: str | None = None
    is_blocking: bool = False
    remediation: str | None = None

    @field_validator("line_number", mode="before")
    @classmethod
    def _coerce_line_number(cls, v: object) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class QualityAgentResponse(BaseModel):
    findings: list[AgentFinding] = Field(default_factory=list)
    summary: str


class SecurityAgentResponse(BaseModel):
    findings: list[AgentFinding] = Field(default_factory=list)
    layer1_detections: list[dict[str, Any]] = Field(default_factory=list)


class DependencyAgentResponse(BaseModel):
    findings: list[AgentFinding] = Field(default_factory=list)
    summary: str


class AgentResult(BaseModel):
    agent_name: str
    success: bool
    findings: list[AgentFinding] = Field(default_factory=list)
    summary: str = ""
    latency_ms: int = 0
    validation_passed: bool = True


class ReviewResult(BaseModel):
    status: Literal["success", "failed"]
    findings_count: int
    latency_ms: int
    quality_findings: int
    security_findings: int
    dependency_findings: int = 0


class APIResponse(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] | None = None


class WebhookResponse(BaseModel):
    success: bool
    message: str
    task_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PREvent(BaseModel):
    event_id: str
    event_type: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    pr_title: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
