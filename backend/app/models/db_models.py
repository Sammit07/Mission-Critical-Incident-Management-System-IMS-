import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


def _now():
    return datetime.now(timezone.utc)


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_id = Column(String(255), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)
    priority = Column(String(10), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="OPEN", index=True)
    title = Column(String(500), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    mttr_seconds = Column(BigInteger, nullable=True)
    signal_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    rca = relationship(
        "RCARecord",
        back_populates="work_item",
        uselist=False,
        cascade="all, delete-orphan",
    )


class RCARecord(Base):
    __tablename__ = "rca_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_start = Column(DateTime(timezone=True), nullable=False)
    incident_end = Column(DateTime(timezone=True), nullable=False)
    root_cause_category = Column(String(100), nullable=False)
    fix_applied = Column(Text, nullable=False)
    prevention_steps = Column(Text, nullable=False)
    submitted_by = Column(String(255), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    work_item = relationship("WorkItem", back_populates="rca")

    __table_args__ = (
        UniqueConstraint("work_item_id", name="uq_rca_per_work_item"),
    )
