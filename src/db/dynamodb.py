from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import aioboto3

from src.config import settings

_session = aioboto3.Session()


@asynccontextmanager
async def dynamodb_resource() -> AsyncGenerator[Any, None]:
    async with _session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url or None,
    ) as resource:
        yield resource


async def ping() -> None:
    async with _session.client(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url or None,
    ) as client:
        await client.describe_table(TableName=settings.dynamodb_pr_events_table)
