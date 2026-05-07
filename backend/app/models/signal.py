from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

ComponentType = Literal["RDBMS", "API", "MCP_HOST", "CACHE", "ASYNC_QUEUE", "NOSQL"]
SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class SignalIngestion(BaseModel):
    component_id: str = Field(..., description="Unique identifier of the failing component")
    component_type: ComponentType
    error_type: str = Field(..., description="Error type (e.g. CONNECTION_TIMEOUT)")
    severity: SeverityLevel
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class SignalResponse(BaseModel):
    signal_id: str
    work_item_id: str
    status: str
    message: str


class BatchSignalIngestion(BaseModel):
    signals: Annotated[list[SignalIngestion], Field(max_length=1000)]
