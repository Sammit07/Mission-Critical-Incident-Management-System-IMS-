from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class WorkItemResponse(BaseModel):
    id: str
    component_id: str
    component_type: str
    priority: str
    status: str
    title: str
    start_time: datetime
    end_time: datetime | None = None
    mttr_seconds: int | None = None
    signal_count: int
    created_at: datetime
    updated_at: datetime
    rca: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: Literal["OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"]
    comment: str | None = None
