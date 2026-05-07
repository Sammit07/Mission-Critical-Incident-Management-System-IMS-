"""
Signal Ingestion Service

Architecture:
  HTTP handler → asyncio.Queue (backpressure buffer) → worker pool → DB writes

Key behaviours:
  • The queue decouples fast ingestion from slower DB writes — the process never
    crashes under load; callers receive 503 only when the queue itself is full.
  • Debouncing uses an atomic Redis SET NX EX so that 100 signals for the same
    component within 10 s produce exactly ONE work item with all signals linked.
  • DB writes use exponential-backoff retry (see utils/retry.py).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import update

from ..config import settings
from ..database import AsyncSessionLocal, get_mongo_db, get_redis
from ..models.db_models import WorkItem
from ..patterns.alert_strategy import AlertContext
from ..utils.retry import with_retry
from .metrics_service import metrics_service
from .websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=settings.SIGNAL_QUEUE_MAXSIZE)
        self._workers: list[asyncio.Task] = []
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        for i in range(settings.SIGNAL_WORKER_COUNT):
            task = asyncio.create_task(self._worker(f"worker-{i}"), name=f"ingestion-{i}")
            self._workers.append(task)
        logger.info("Started %d ingestion workers", settings.SIGNAL_WORKER_COUNT)

    async def stop(self) -> None:
        self._running = False
        for t in self._workers:
            t.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Ingestion workers stopped")

    # ── Public API ────────────────────────────────────────────────────────────

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def is_queue_full(self) -> bool:
        return self._queue.full()

    async def enqueue(self, signal_data: dict) -> tuple[str, bool]:
        """
        Returns (signal_id, was_queued).
        was_queued=False signals backpressure — callers should return 503.
        """
        if self._queue.full():
            logger.warning("Queue full — applying backpressure (depth=%d)", self._queue.qsize())
            return str(uuid.uuid4()), False

        signal_id = str(uuid.uuid4())
        signal_data["signal_id"] = signal_id
        signal_data["received_at"] = datetime.now(timezone.utc).isoformat()

        await self._queue.put(signal_data)
        await metrics_service.record_signal()
        return signal_id, True

    # ── Worker ────────────────────────────────────────────────────────────────

    async def _worker(self, name: str) -> None:
        logger.info("%s started", name)
        while self._running:
            try:
                signal_data = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                try:
                    await self._process_signal(signal_data)
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("%s: unhandled error processing signal", name)
        logger.info("%s stopped", name)

    # ── Signal processing ─────────────────────────────────────────────────────

    async def _process_signal(self, signal_data: dict) -> None:
        component_id = signal_data["component_id"]
        component_type = signal_data["component_type"]
        signal_id = signal_data["signal_id"]
        tentative_id = str(uuid.uuid4())

        work_item_id, is_new = await self._get_or_create_work_item_id(component_id, tentative_id)

        # Mongo audit log before Postgres counter — prevents phantom counts when Mongo is down
        await self._store_raw_signal(signal_id, work_item_id, signal_data)

        try:
            redis = get_redis()
            await redis.ts().add(f"signals:{component_type}", "*", 1, duplicate_policy="sum")
        except Exception:
            pass  # Redis TimeSeries unavailable — degrade gracefully

        if is_new:
            await self._create_work_item(work_item_id, signal_data)
        else:
            await self._increment_signal_count(work_item_id)

        await websocket_manager.broadcast({
            "type": "signal_received",
            "work_item_id": work_item_id,
            "component_id": component_id,
            "severity": signal_data.get("severity"),
            "is_new_incident": is_new,
        })

    async def _get_or_create_work_item_id(
        self, component_id: str, tentative_id: str
    ) -> tuple[str, bool]:
        """
        Atomic debounce via Redis SET NX EX.
        Returns (work_item_id, is_new_work_item).
        """
        redis = get_redis()
        key = f"debounce:{component_id}"

        was_set = await redis.set(
            key, tentative_id, nx=True, ex=settings.DEBOUNCE_WINDOW_SECONDS
        )
        if was_set:
            return tentative_id, True

        existing = await redis.get(key)
        if existing:
            return existing, False

        # Extremely rare: key expired between SET and GET — treat as new
        await redis.set(key, tentative_id, ex=settings.DEBOUNCE_WINDOW_SECONDS)
        return tentative_id, True

    @with_retry(max_attempts=3, initial_delay=0.1)
    async def _create_work_item(self, work_item_id: str, signal_data: dict) -> None:
        component_type = signal_data["component_type"]
        component_id = signal_data["component_id"]

        alert_ctx = AlertContext()
        alert_ctx.set_strategy_for_component(component_type)
        priority = alert_ctx.get_priority()

        # Fire alert (logs to console; in prod, would call PagerDuty/Slack)
        await alert_ctx.alert(component_id, component_type, signal_data.get("message", ""))

        work_item = WorkItem(
            id=uuid.UUID(work_item_id),
            component_id=component_id,
            component_type=component_type,
            priority=priority,
            status="OPEN",
            title=f"[{priority}] {component_type} failure: {component_id}",
            start_time=datetime.now(timezone.utc),
            signal_count=1,
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(work_item)

        await metrics_service.record_work_item()
        await self._cache_incident(work_item_id, component_id, component_type, priority, "OPEN")

        await websocket_manager.broadcast({
            "type": "incident_created",
            "work_item_id": work_item_id,
            "component_id": component_id,
            "component_type": component_type,
            "priority": priority,
            "title": work_item.title,
        })
        logger.info("Created work item %s [%s] for %s", work_item_id, priority, component_id)

    @with_retry(max_attempts=3, initial_delay=0.1)
    async def _increment_signal_count(self, work_item_id: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(WorkItem)
                    .where(WorkItem.id == uuid.UUID(work_item_id))
                    .values(
                        signal_count=WorkItem.signal_count + 1,
                        updated_at=datetime.now(timezone.utc),
                    )
                )

    @with_retry(max_attempts=3, initial_delay=0.1)
    async def _store_raw_signal(
        self, signal_id: str, work_item_id: str, signal_data: dict
    ) -> None:
        mongo_db = get_mongo_db()
        doc = {
            "signal_id": signal_id,
            "work_item_id": work_item_id,
            "component_id": signal_data["component_id"],
            "component_type": signal_data["component_type"],
            "error_type": signal_data.get("error_type"),
            "severity": signal_data.get("severity"),
            "message": signal_data.get("message"),
            "metadata": signal_data.get("metadata", {}),
            "timestamp": signal_data.get("timestamp") or signal_data["received_at"],
            "received_at": signal_data["received_at"],
        }
        await mongo_db.signals.insert_one(doc)

    async def _cache_incident(
        self, work_item_id: str, component_id: str,
        component_type: str, priority: str, status: str,
    ) -> None:
        redis = get_redis()
        await redis.hset(
            f"dashboard:incident:{work_item_id}",
            mapping={
                "work_item_id": work_item_id,
                "component_id": component_id,
                "component_type": component_type,
                "priority": priority,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await redis.expire(f"dashboard:incident:{work_item_id}", 86400)


ingestion_service = IngestionService()
