"""
State Pattern — Incident Lifecycle

Work items move through a strict state machine:
  OPEN → INVESTIGATING → RESOLVED → CLOSED

Each state encodes its own allowed transitions. ClosedState additionally
validates that a complete RCA exists before allowing the transition.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Valid outgoing transitions for each status
VALID_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"INVESTIGATING"},
    "INVESTIGATING": {"RESOLVED", "OPEN"},
    "RESOLVED": {"CLOSED", "INVESTIGATING"},
    "CLOSED": set(),
}


class IncidentState(ABC):
    @abstractmethod
    def get_name(self) -> str: ...

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.get_name(), set())

    def validate_entry(self, work_item_data: dict) -> None:
        """Override to add pre-entry validation for a state."""


class OpenState(IncidentState):
    def get_name(self) -> str:
        return "OPEN"


class InvestigatingState(IncidentState):
    def get_name(self) -> str:
        return "INVESTIGATING"


class ResolvedState(IncidentState):
    def get_name(self) -> str:
        return "RESOLVED"


class ClosedState(IncidentState):
    def get_name(self) -> str:
        return "CLOSED"

    def validate_entry(self, work_item_data: dict) -> None:
        """Mandatory RCA check — the system must reject CLOSED without a complete RCA."""
        rca = work_item_data.get("rca")
        if not rca:
            raise ValueError(
                "Cannot close incident: RCA record is missing. "
                "Submit an RCA via POST /api/incidents/{id}/rca first."
            )
        required = ["root_cause_category", "fix_applied", "prevention_steps",
                    "incident_start", "incident_end"]
        missing = [f for f in required if not rca.get(f)]
        if missing:
            raise ValueError(
                f"Cannot close incident: RCA is incomplete. "
                f"Missing fields: {', '.join(missing)}"
            )


_STATE_MAP: dict[str, type[IncidentState]] = {
    "OPEN": OpenState,
    "INVESTIGATING": InvestigatingState,
    "RESOLVED": ResolvedState,
    "CLOSED": ClosedState,
}


class WorkItemStateMachine:
    """
    Wraps the current IncidentState and enforces legal transitions.
    Raises ValueError for illegal transitions or failed entry validation.
    """

    def __init__(self, current_status: str) -> None:
        state_cls = _STATE_MAP.get(current_status, OpenState)
        self._state: IncidentState = state_cls()

    def transition_to(self, new_status: str, work_item_data: dict) -> None:
        if not self._state.can_transition_to(new_status):
            allowed = VALID_TRANSITIONS.get(self._state.get_name(), set())
            raise ValueError(
                f"Invalid transition: {self._state.get_name()} → {new_status}. "
                f"Allowed from {self._state.get_name()}: {allowed or 'none (terminal state)'}"
            )

        new_state_cls = _STATE_MAP.get(new_status)
        if not new_state_cls:
            raise ValueError(f"Unknown status: {new_status}")

        new_state = new_state_cls()
        new_state.validate_entry(work_item_data)

        logger.info("Work item state: %s → %s", self._state.get_name(), new_status)
        self._state = new_state

    def current_status(self) -> str:
        return self._state.get_name()
