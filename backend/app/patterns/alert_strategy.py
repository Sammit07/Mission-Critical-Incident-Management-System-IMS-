"""
Strategy Pattern — Alerting

Each component type maps to a concrete AlertStrategy that encodes
the appropriate priority level and notification channel. The AlertContext
selects and executes the right strategy at runtime based on component type.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class AlertResult:
    priority: str
    channel: str
    message: str
    notified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertStrategy(ABC):
    @abstractmethod
    def get_priority(self) -> str: ...

    @abstractmethod
    async def execute(
        self, component_id: str, component_type: str, error_message: str
    ) -> AlertResult: ...


class P0CriticalAlert(AlertStrategy):
    """P0 — RDBMS failures: page on-call immediately via all channels."""

    def get_priority(self) -> str:
        return "P0"

    async def execute(self, component_id: str, component_type: str, error_message: str) -> AlertResult:
        msg = (
            f"[P0-CRITICAL] {component_type} failure on {component_id}. "
            f"Immediate response required! {error_message}"
        )
        logger.critical(msg)
        return AlertResult(priority="P0", channel="pagerduty+slack:#incidents-critical+sms", message=msg)


class P1HighAlert(AlertStrategy):
    """P1 — API / MCP_HOST failures: page on-call, respond within 15 min."""

    def get_priority(self) -> str:
        return "P1"

    async def execute(self, component_id: str, component_type: str, error_message: str) -> AlertResult:
        msg = (
            f"[P1-HIGH] {component_type} failure on {component_id}. "
            f"Response required within 15 minutes. {error_message}"
        )
        logger.error(msg)
        return AlertResult(priority="P1", channel="pagerduty+slack:#incidents-high", message=msg)


class P2MediumAlert(AlertStrategy):
    """P2 — CACHE degradation: Slack notification, review within 1 hour."""

    def get_priority(self) -> str:
        return "P2"

    async def execute(self, component_id: str, component_type: str, error_message: str) -> AlertResult:
        msg = (
            f"[P2-MEDIUM] {component_type} degradation on {component_id}. "
            f"Review within 1 hour. {error_message}"
        )
        logger.warning(msg)
        return AlertResult(priority="P2", channel="slack:#incidents-medium", message=msg)


class P3LowAlert(AlertStrategy):
    """P3 — ASYNC_QUEUE / NOSQL issues: create ticket, review in sprint."""

    def get_priority(self) -> str:
        return "P3"

    async def execute(self, component_id: str, component_type: str, error_message: str) -> AlertResult:
        msg = (
            f"[P3-LOW] {component_type} issue on {component_id}. "
            f"Review in next sprint. {error_message}"
        )
        logger.info(msg)
        return AlertResult(priority="P3", channel="jira+slack:#incidents-low", message=msg)


# Maps component type → strategy class (swappable at runtime)
COMPONENT_ALERT_MAP: dict[str, type[AlertStrategy]] = {
    "RDBMS": P0CriticalAlert,
    "API": P1HighAlert,
    "MCP_HOST": P1HighAlert,
    "CACHE": P2MediumAlert,
    "ASYNC_QUEUE": P3LowAlert,
    "NOSQL": P3LowAlert,
}


class AlertContext:
    """
    Context that holds a concrete AlertStrategy and delegates execution to it.
    Strategies are swapped by calling set_strategy_for_component().
    """

    def __init__(self) -> None:
        self._strategy: AlertStrategy = P3LowAlert()

    def set_strategy_for_component(self, component_type: str) -> None:
        strategy_cls = COMPONENT_ALERT_MAP.get(component_type, P3LowAlert)
        self._strategy = strategy_cls()

    def get_priority(self) -> str:
        return self._strategy.get_priority()

    async def alert(
        self, component_id: str, component_type: str, error_message: str
    ) -> AlertResult:
        return await self._strategy.execute(component_id, component_type, error_message)
