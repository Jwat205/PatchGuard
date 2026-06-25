from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PREvent(BaseModel):
    event_id: str
    event_type: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReviewEvent(BaseModel):
    event_id: str
    review_id: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    agent_name: str
    findings_count: int
    validation_passed: bool
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
