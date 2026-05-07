from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RootCauseCategory = Literal[
    "HUMAN_ERROR",
    "SOFTWARE_BUG",
    "INFRASTRUCTURE_FAILURE",
    "CAPACITY_EXHAUSTION",
    "EXTERNAL_DEPENDENCY",
    "SECURITY_INCIDENT",
    "CONFIGURATION_ERROR",
]


class RCASubmission(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    fix_applied: str = Field(..., min_length=10, description="Description of the fix applied")
    prevention_steps: str = Field(..., min_length=10, description="Steps to prevent recurrence")
    submitted_by: str | None = None


class RCAResponse(BaseModel):
    id: str
    work_item_id: str
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str
    submitted_by: str | None = None
    submitted_at: datetime
    mttr_seconds: int
