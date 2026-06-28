from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import reviews, webhooks, ping
from src.db.database import create_tables, dispose_engine
from src.db.mongodb import close_mongo
from src.db.redis_client import close_redis
from src.services.monitoring import metrics_app
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("PatchGuard starting up")
    await create_tables()
    yield
    logger.info("PatchGuard shutting down")
    await close_redis()
    await close_mongo()
    await dispose_engine()


app = FastAPI(
    title="PatchGuard",
    description="Autonomous GitHub PR code review agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REMOVE the old health router
# app.include_router(health.router)

# KEEP the correct health router
app.include_router(ping.router)

app.include_router(webhooks.router)
app.include_router(reviews.router)

app.mount("/metrics", metrics_app)


@app.get("/")
async def root() -> dict:
    return {"service": "PatchGuard", "status": "running"}
