"""
Unit tests for RCASubmission date validation.

Verifies that inverted dates (end <= start) are rejected at the Pydantic
model level before reaching any service code.
"""
import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from app.models.rca import RCASubmission

_BASE = {
    "root_cause_category": "SOFTWARE_BUG",
    "fix_applied": "Rolled back the bad deploy",
    "prevention_steps": "Add integration tests for this code path",
}

_START = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
_END   = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_valid_dates_accepted():
    rca = RCASubmission(incident_start=_START, incident_end=_END, **_BASE)
    assert rca.incident_end > rca.incident_start


def test_inverted_dates_raises():
    """end before start must be rejected."""
    with pytest.raises(ValidationError, match="incident_end must be after incident_start"):
        RCASubmission(incident_start=_END, incident_end=_START, **_BASE)


def test_equal_dates_raises():
    """end == start is also invalid (zero MTTR is meaningless)."""
    with pytest.raises(ValidationError, match="incident_end must be after incident_start"):
        RCASubmission(incident_start=_START, incident_end=_START, **_BASE)


def test_one_second_apart_accepted():
    """Minimum valid duration is 1 second."""
    rca = RCASubmission(
        incident_start=_START,
        incident_end=_START + timedelta(seconds=1),
        **_BASE,
    )
    assert rca.incident_end > rca.incident_start


def test_mttr_not_negative():
    """MTTR derived from valid dates is always positive."""
    rca = RCASubmission(incident_start=_START, incident_end=_END, **_BASE)
    mttr = int((rca.incident_end - rca.incident_start).total_seconds())
    assert mttr > 0
