"""
IMS — Incident Management System
FastAPI application entry point.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import close_connections, init_mongodb, init_postgres, init_redis
from .middleware.rate_limiter import RateLimiterMiddleware
from .services.ingestion_service import ingestion_service
from .services.metrics_service import metrics_service
from .api import health, incidents, signals, websocket_handler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== IMS starting up ===")
    await init_redis()
    await init_postgres()
    await init_mongodb()
    await ingestion_service.start()

    metrics_task = asyncio.create_task(
        metrics_service.start_periodic_reporting(settings.METRICS_INTERVAL_SECONDS),
        name="metrics-reporter",
    )

    logger.info("=== IMS ready — accepting signals ===")
    yield

    logger.info("=== IMS shutting down ===")
    metrics_service.stop()
    metrics_task.cancel()
    await asyncio.gather(metrics_task, return_exceptions=True)
    await ingestion_service.stop()
    await close_connections()
    logger.info("=== IMS shutdown complete ===")


app = FastAPI(
    title="Incident Management System",
    description=(
        "Mission-critical IMS for monitoring distributed infrastructure. "
        "Ingests high-volume failure signals, debounces them into work items, "
        "and provides a workflow-driven UI to track incidents to closure with mandatory RCA."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dashboard to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sliding-window rate limiter on /api/signals
app.add_middleware(
    RateLimiterMiddleware,
    requests_per_window=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)

app.include_router(signals.router)
app.include_router(incidents.router)
app.include_router(health.router)
app.include_router(websocket_handler.router)
