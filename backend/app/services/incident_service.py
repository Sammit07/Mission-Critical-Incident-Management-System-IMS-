"""
Incident (Work Item) service — CRUD + state transitions + RCA submission.

All status transitions go through the WorkItemStateMachine, which enforces
the OPEN → INVESTIGATING → RESOLVED → CLOSED lifecycle and blocks CLOSED
unless a complete RCA record exists (mandatory RCA gate).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..database import AsyncSessionLocal, get_redis
from ..models.db_models import RCARecord, WorkItem
from ..models.rca import RCASubmission
from ..patterns.incident_state import WorkItemStateMachine
from ..utils.retry import with_retry
from .websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class IncidentService:

    async def list_incidents(
        self,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        async with AsyncSessionLocal() as session:
            q = select(WorkItem).options(selectinload(WorkItem.rca))
            if status:
                q = q.where(WorkItem.status == status)
            if priority:
                q = q.where(WorkItem.priority == priority)
            # P0 first (alphabetical on "P0"–"P3" works correctly)
            q = q.order_by(WorkItem.priority.asc(), WorkItem.created_at.desc())
            q = q.limit(limit).offset(offset)

            result = await session.execute(q)
            return [self._serialize(wi) for wi in result.scalars().all()]

    async def get_incident(self, work_item_id: str) -> dict | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WorkItem)
                .options(selectinload(WorkItem.rca))
                .where(WorkItem.id == uuid.UUID(work_item_id))
            )
            wi = result.scalar_one_or_none()
            return self._serialize(wi) if wi else None

    @with_retry(max_attempts=3, initial_delay=0.1)
    async def update_status(self, work_item_id: str, new_status: str) -> dict:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(WorkItem)
                    .options(selectinload(WorkItem.rca))
                    .where(WorkItem.id == uuid.UUID(work_item_id))
                    .with_for_update()  # pessimistic lock prevents concurrent state corruption
                )
                wi = result.scalar_one_or_none()
                if not wi:
                    raise ValueError(f"Work item {work_item_id} not found")

                sm = WorkItemStateMachine(wi.status)
                sm.transition_to(new_status, self._serialize(wi))

                now = datetime.now(timezone.utc)
                wi.status = new_status
                wi.updated_at = now

                if new_status == "CLOSED" and wi.rca:
                    wi.end_time = now
                    delta = wi.rca.incident_end - wi.rca.incident_start
                    wi.mttr_seconds = int(abs(delta.total_seconds()))

                serialized = self._serialize(wi)

        await self._update_cache(work_item_id, new_status)
        await websocket_manager.broadcast({
            "type": "incident_updated",
            "work_item_id": work_item_id,
            "status": new_status,
        })
        return serialized

    @with_retry(max_attempts=3, initial_delay=0.1)
    async def submit_rca(self, work_item_id: str, rca_data: RCASubmission) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(WorkItem)
                    .where(WorkItem.id == uuid.UUID(work_item_id))
                    .with_for_update()
                )
                wi = result.scalar_one_or_none()
                if not wi:
                    raise ValueError(f"Work item {work_item_id} not found")
                if wi.status == "CLOSED":
                    raise ValueError("Cannot modify RCA of a closed incident")

                existing_result = await session.execute(
                    select(RCARecord).where(RCARecord.work_item_id == uuid.UUID(work_item_id))
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    existing.incident_start = rca_data.incident_start
                    existing.incident_end = rca_data.incident_end
                    existing.root_cause_category = rca_data.root_cause_category
                    existing.fix_applied = rca_data.fix_applied
                    existing.prevention_steps = rca_data.prevention_steps
                    existing.submitted_by = rca_data.submitted_by
                    existing.submitted_at = datetime.now(timezone.utc)
                else:
                    session.add(RCARecord(
                        work_item_id=uuid.UUID(work_item_id),
                        incident_start=rca_data.incident_start,
                        incident_end=rca_data.incident_end,
                        root_cause_category=rca_data.root_cause_category,
                        fix_applied=rca_data.fix_applied,
                        prevention_steps=rca_data.prevention_steps,
                        submitted_by=rca_data.submitted_by,
                    ))

        mttr = int(abs((rca_data.incident_end - rca_data.incident_start).total_seconds()))
        await websocket_manager.broadcast({"type": "rca_submitted", "work_item_id": work_item_id})

        return {
            "work_item_id": work_item_id,
            "root_cause_category": rca_data.root_cause_category,
            "mttr_seconds": mttr,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "message": "RCA submitted. You may now close this incident.",
        }

    async def get_signals(self, work_item_id: str, limit: int = 100, skip: int = 0) -> list[dict]:
        from ..database import get_mongo_db
        mongo_db = get_mongo_db()
        docs = await (
            mongo_db.signals
            .find({"work_item_id": work_item_id}, {"_id": 0})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
            .to_list(limit)
        )
        return docs

    async def _update_cache(self, work_item_id: str, status: str) -> None:
        redis = get_redis()
        if redis:
            await redis.hset(
                f"dashboard:incident:{work_item_id}",
                mapping={"status": status, "updated_at": datetime.now(timezone.utc).isoformat()},
            )

    def _serialize(self, wi: WorkItem) -> dict:
        data: dict[str, Any] = {
            "id": str(wi.id),
            "component_id": wi.component_id,
            "component_type": wi.component_type,
            "priority": wi.priority,
            "status": wi.status,
            "title": wi.title,
            "start_time": wi.start_time.isoformat() if wi.start_time else None,
            "end_time": wi.end_time.isoformat() if wi.end_time else None,
            "mttr_seconds": wi.mttr_seconds,
            "signal_count": wi.signal_count,
            "created_at": wi.created_at.isoformat() if wi.created_at else None,
            "updated_at": wi.updated_at.isoformat() if wi.updated_at else None,
            "rca": None,
        }
        if wi.rca:
            data["rca"] = {
                "id": str(wi.rca.id),
                "incident_start": wi.rca.incident_start.isoformat(),
                "incident_end": wi.rca.incident_end.isoformat(),
                "root_cause_category": wi.rca.root_cause_category,
                "fix_applied": wi.rca.fix_applied,
                "prevention_steps": wi.rca.prevention_steps,
                "submitted_by": wi.rca.submitted_by,
                "submitted_at": wi.rca.submitted_at.isoformat(),
            }
        return data


incident_service = IncidentService()
