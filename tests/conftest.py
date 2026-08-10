import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.db.database import Base, get_db
from src.main import app
from src.models.schemas import AgentFinding, AgentResult

# ── In-memory SQLite engine for tests ─────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def mock_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db_session

    with patch("src.db.redis_client.get_redis", return_value=mock_redis):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def webhook_secret():
    return "test_webhook_secret"


@pytest.fixture
def valid_pr_payload() -> dict:
    return {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "title": "Add feature X",
            "head": {"sha": "abc123def456"},
            "base": {"sha": "base000"},
        },
        "repository": {"full_name": "owner/repo"},
        "installation": {"id": 1},
    }


@pytest.fixture
def make_signature(webhook_secret):
    def _sign(body: bytes) -> str:
        sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    return _sign


@pytest.fixture
def sample_diff() -> str:
    return """diff --git a/auth.py b/auth.py
--- a/auth.py
+++ b/auth.py
@@ -1,5 +1,10 @@
+import jwt
+
+SECRET = 'hardcoded_secret'
+
+def decode_token(token):
+    return jwt.decode(token, SECRET, algorithms=['none'])
"""


@pytest.fixture
def mock_quality_result() -> AgentResult:
    return AgentResult(
        agent_name="quality",
        success=True,
        findings=[
            AgentFinding(
                file_path="main.py",
                line_number=10,
                finding_type="missing_test",
                severity="warning",
                message="No tests for changed function",
            )
        ],
        summary="One quality issue found",
        latency_ms=500,
        validation_passed=True,
    )


@pytest.fixture
def mock_security_result() -> AgentResult:
    return AgentResult(
        agent_name="security",
        success=True,
        findings=[
            AgentFinding(
                file_path="auth.py",
                line_number=6,
                finding_type="jwt_algorithm_confusion",
                severity="critical",
                message="JWT decoded with 'none' algorithm",
                is_blocking=True,
                remediation="Specify allowed algorithms explicitly",
            )
        ],
        summary="Critical JWT vulnerability found",
        latency_ms=700,
        validation_passed=True,
    )
