from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import reviews, webhooks, ping, health
from src.db.database import create_tables, dispose_engine
from src.db.mongodb import close_mongo
from src.db.redis_client import close_redis
from src.services.monitoring import metrics_app
from src.utils.logging import get_logger, setup_logging
from src.config import settings

setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PatchGuard starting up")
    print("SERVER JWT SECRET:", settings.jwt_secret_key)
    await create_tables()
    yield
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

app.include_router(health.router)
app.include_router(ping.router)
app.include_router(webhooks.router)
app.include_router(reviews.router)

app.mount("/metrics", metrics_app)


@app.get("/debug-token")
async def debug_token(request: Request):
    auth_header = request.headers.get("authorization", "")
    print(f"DEBUG: Authorization header = {auth_header}")
    return {"header": auth_header}

