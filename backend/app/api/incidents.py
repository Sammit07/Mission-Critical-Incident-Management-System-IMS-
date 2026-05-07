from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.incident import StatusUpdateRequest, WorkItemResponse
from ..models.rca import RCASubmission
from ..services.incident_service import incident_service

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[WorkItemResponse])
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority (P0–P3)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List work items sorted by priority (P0 first) then recency."""
    return await incident_service.list_incidents(status, priority, limit, offset)


@router.get("/{work_item_id}", response_model=WorkItemResponse)
async def get_incident(work_item_id: str):
    incident = await incident_service.get_incident(work_item_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{work_item_id}/status")
async def update_status(work_item_id: str, body: StatusUpdateRequest):
    """
    Transition a work item through the state machine.
    CLOSED is rejected unless a complete RCA exists.
    """
    try:
        return await incident_service.update_status(work_item_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{work_item_id}/rca")
async def submit_rca(work_item_id: str, rca: RCASubmission):
    """Submit or update the Root Cause Analysis for an incident."""
    try:
        return await incident_service.submit_rca(work_item_id, rca)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{work_item_id}/signals")
async def get_signals(
    work_item_id: str,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    """Fetch raw signal payloads (audit log) from MongoDB for an incident."""
    signals = await incident_service.get_signals(work_item_id, limit=limit, skip=skip)
    return {"work_item_id": work_item_id, "count": len(signals), "signals": signals}
