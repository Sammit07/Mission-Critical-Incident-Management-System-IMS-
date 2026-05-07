import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..database import engine, get_mongo_db, get_redis
from ..services.ingestion_service import ingestion_service
from ..services.metrics_service import metrics_service
from ..services.websocket_manager import websocket_manager

_COMPONENT_TYPES = ["RDBMS", "API", "MCP_HOST", "CACHE", "ASYNC_QUEUE", "NOSQL"]

router = APIRouter(tags=["observability"])


@router.get("/health")
async def health_check():
    """
    Liveness + readiness probe.
    Returns 200 with status='healthy' when all backends are reachable.
    """
    checks: dict[str, str | int] = {}

    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as exc:
        checks["postgres"] = f"unhealthy: {exc}"

    # Redis
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as exc:
        checks["redis"] = f"unhealthy: {exc}"

    # MongoDB
    try:
        mongo = get_mongo_db()
        await mongo.command("ping")
        checks["mongodb"] = "healthy"
    except Exception as exc:
        checks["mongodb"] = f"unhealthy: {exc}"

    checks["queue_depth"] = ingestion_service.queue_depth()
    checks["ws_connections"] = websocket_manager.connection_count()

    all_healthy = all(
        checks[k] == "healthy" for k in ("postgres", "redis", "mongodb")
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/metrics")
async def get_metrics():
    """Real-time throughput metrics."""
    stats = metrics_service.get_stats()
    stats["queue_depth"] = ingestion_service.queue_depth()
    stats["ws_connections"] = websocket_manager.connection_count()
    return stats


@router.get("/api/metrics/timeseries")
async def get_timeseries(minutes: int = Query(60, ge=1, le=1440)):
    """
    Per-component-type signal counts over time, bucketed by minute.
    Reads from Redis TimeSeries (requires redis-stack image).
    Returns {component_type: [{ts: epoch_ms, value: count}, ...], ...}.
    """
    redis = get_redis()
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - minutes * 60 * 1000
    bucket_ms = 60 * 1000

    result: dict = {}
    for ctype in _COMPONENT_TYPES:
        try:
            points = await redis.ts().range(
                f"signals:{ctype}", start_ms, end_ms,
                aggregation_type="sum", bucket_size_msec=bucket_ms,
            )
            result[ctype] = [{"ts": ts, "value": val} for ts, val in points]
        except Exception:
            result[ctype] = []
    return result


@router.get("/api/metrics/top-components")
async def top_components(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(10, ge=1, le=50),
):
    """Top N noisiest components by signal count over the last N hours (MongoDB aggregation)."""
    mongo_db = get_mongo_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$match": {"received_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$component_id",
            "component_type": {"$first": "$component_type"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    docs = await mongo_db.signals.aggregate(pipeline).to_list(length=limit)
    return [
        {"component_id": d["_id"], "component_type": d["component_type"], "count": d["count"]}
        for d in docs
    ]
