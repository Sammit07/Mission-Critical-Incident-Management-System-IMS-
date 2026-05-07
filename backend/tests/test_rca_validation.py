"""
Unit tests for the RCA validation logic in the State pattern.

These tests verify that the mandatory-RCA gate works correctly:
  - Transitioning to CLOSED without an RCA raises ValueError
  - Transitioning to CLOSED with an incomplete RCA raises ValueError
  - Transitioning to CLOSED with a valid RCA succeeds
  - All other state transitions are tested for correctness
"""
import pytest

from app.patterns.incident_state import WorkItemStateMachine


def _work_item(status: str, rca: dict | None = None) -> dict:
    return {"status": status, "rca": rca}


def _complete_rca() -> dict:
    return {
        "root_cause_category": "SOFTWARE_BUG",
        "fix_applied": "Rolled back to v1.2.3",
        "prevention_steps": "Add integration test for connection pool exhaustion",
        "incident_start": "2024-01-15T10:00:00Z",
        "incident_end": "2024-01-15T12:00:00Z",
    }


# ── Happy-path transitions ────────────────────────────────────────────────────

def test_open_to_investigating():
    sm = WorkItemStateMachine("OPEN")
    sm.transition_to("INVESTIGATING", _work_item("OPEN"))
    assert sm.current_status() == "INVESTIGATING"


def test_investigating_to_resolved():
    sm = WorkItemStateMachine("INVESTIGATING")
    sm.transition_to("RESOLVED", _work_item("INVESTIGATING"))
    assert sm.current_status() == "RESOLVED"


def test_resolved_to_closed_with_rca():
    sm = WorkItemStateMachine("RESOLVED")
    sm.transition_to("CLOSED", _work_item("RESOLVED", rca=_complete_rca()))
    assert sm.current_status() == "CLOSED"


def test_investigating_can_reopen():
    sm = WorkItemStateMachine("INVESTIGATING")
    sm.transition_to("OPEN", _work_item("INVESTIGATING"))
    assert sm.current_status() == "OPEN"


def test_resolved_can_revert_to_investigating():
    sm = WorkItemStateMachine("RESOLVED")
    sm.transition_to("INVESTIGATING", _work_item("RESOLVED"))
    assert sm.current_status() == "INVESTIGATING"


# ── RCA gate ──────────────────────────────────────────────────────────────────

def test_closed_without_rca_raises():
    sm = WorkItemStateMachine("RESOLVED")
    with pytest.raises(ValueError, match="RCA record is missing"):
        sm.transition_to("CLOSED", _work_item("RESOLVED", rca=None))


def test_closed_with_incomplete_rca_raises():
    incomplete = _complete_rca()
    del incomplete["fix_applied"]
    sm = WorkItemStateMachine("RESOLVED")
    with pytest.raises(ValueError, match="incomplete"):
        sm.transition_to("CLOSED", _work_item("RESOLVED", rca=incomplete))


def test_closed_with_empty_field_raises():
    rca = _complete_rca()
    rca["prevention_steps"] = ""
    sm = WorkItemStateMachine("RESOLVED")
    with pytest.raises(ValueError):
        sm.transition_to("CLOSED", _work_item("RESOLVED", rca=rca))


# ── Illegal transitions ───────────────────────────────────────────────────────

def test_open_cannot_skip_to_resolved():
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.transition_to("RESOLVED", _work_item("OPEN"))


def test_open_cannot_jump_to_closed():
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.transition_to("CLOSED", _work_item("OPEN", rca=_complete_rca()))


def test_closed_is_terminal():
    sm = WorkItemStateMachine("CLOSED")
    with pytest.raises(ValueError, match="terminal"):
        sm.transition_to("RESOLVED", _work_item("CLOSED"))


def test_unknown_status_raises():
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError):
        sm.transition_to("ARCHIVED", _work_item("OPEN"))
