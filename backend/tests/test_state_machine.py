"""
Unit tests for the two trickiest state-machine correctness properties:

  1. OPEN → CLOSED is rejected by the state guard (illegal skip, not RCA issue).
  2. The full happy path is the only valid route to CLOSED.

See test_rca_validation.py for exhaustive RCA-gate and illegal-transition coverage.
"""
import pytest

from app.patterns.incident_state import WorkItemStateMachine


def _complete_rca() -> dict:
    return {
        "root_cause_category": "SOFTWARE_BUG",
        "fix_applied": "Rolled back to v1.2.3",
        "prevention_steps": "Add integration test for connection pool exhaustion",
        "incident_start": "2024-01-15T10:00:00Z",
        "incident_end": "2024-01-15T12:00:00Z",
    }


def test_open_to_closed_raises_state_guard():
    """OPEN → CLOSED must raise ValueError — state guard blocks the skip, even with a valid RCA."""
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError):
        sm.transition_to("CLOSED", {"status": "OPEN", "rca": _complete_rca()})


def test_open_to_closed_raises_without_rca():
    """Confirm the state guard fires before the RCA gate — no RCA needed to see the error."""
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError):
        sm.transition_to("CLOSED", {"status": "OPEN", "rca": None})


def test_closed_is_terminal_from_all_states():
    """Once CLOSED, every outgoing transition raises ValueError (terminal state)."""
    sm = WorkItemStateMachine("CLOSED")
    for target in ("OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"):
        with pytest.raises(ValueError):
            sm.transition_to(target, {"status": "CLOSED", "rca": _complete_rca()})


def test_full_happy_path_reaches_closed():
    """OPEN → INVESTIGATING → RESOLVED → CLOSED is the only valid path to CLOSED."""
    sm = WorkItemStateMachine("OPEN")
    sm.transition_to("INVESTIGATING", {"status": "OPEN"})
    assert sm.current_status() == "INVESTIGATING"

    sm.transition_to("RESOLVED", {"status": "INVESTIGATING"})
    assert sm.current_status() == "RESOLVED"

    sm.transition_to("CLOSED", {"status": "RESOLVED", "rca": _complete_rca()})
    assert sm.current_status() == "CLOSED"


def test_skip_steps_raises():
    """Any attempt to skip INVESTIGATING is rejected."""
    sm = WorkItemStateMachine("OPEN")
    with pytest.raises(ValueError):
        sm.transition_to("RESOLVED", {"status": "OPEN"})
