from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PREvent(BaseModel):
    event_id: str
    event_type: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_item(self) -> dict[str, Any]:
        item = self.model_dump()
        item["timestamp"] = self.timestamp.isoformat()
        return item


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_item(self) -> dict[str, Any]:
        item = self.model_dump()
        item["timestamp"] = self.timestamp.isoformat()
        return item
