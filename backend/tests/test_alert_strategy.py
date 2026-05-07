"""Unit tests for the Strategy pattern — alert priority selection."""
import pytest

from app.patterns.alert_strategy import (
    AlertContext,
    COMPONENT_ALERT_MAP,
    P0CriticalAlert,
    P1HighAlert,
    P2MediumAlert,
    P3LowAlert,
)


@pytest.mark.asyncio
async def test_rdbms_gets_p0():
    ctx = AlertContext()
    ctx.set_strategy_for_component("RDBMS")
    assert ctx.get_priority() == "P0"
    result = await ctx.alert("DB_PROD_01", "RDBMS", "Connection refused")
    assert result.priority == "P0"


@pytest.mark.asyncio
async def test_api_gets_p1():
    ctx = AlertContext()
    ctx.set_strategy_for_component("API")
    assert ctx.get_priority() == "P1"


@pytest.mark.asyncio
async def test_mcp_host_gets_p1():
    ctx = AlertContext()
    ctx.set_strategy_for_component("MCP_HOST")
    assert ctx.get_priority() == "P1"


@pytest.mark.asyncio
async def test_cache_gets_p2():
    ctx = AlertContext()
    ctx.set_strategy_for_component("CACHE")
    assert ctx.get_priority() == "P2"
    result = await ctx.alert("CACHE_01", "CACHE", "Eviction rate spike")
    assert result.priority == "P2"


@pytest.mark.asyncio
async def test_async_queue_gets_p3():
    ctx = AlertContext()
    ctx.set_strategy_for_component("ASYNC_QUEUE")
    assert ctx.get_priority() == "P3"


@pytest.mark.asyncio
async def test_nosql_gets_p3():
    ctx = AlertContext()
    ctx.set_strategy_for_component("NOSQL")
    assert ctx.get_priority() == "P3"


@pytest.mark.asyncio
async def test_unknown_component_defaults_to_p3():
    ctx = AlertContext()
    ctx.set_strategy_for_component("UNKNOWN_SERVICE")
    assert ctx.get_priority() == "P3"


def test_all_component_types_have_strategy():
    for component_type in ("RDBMS", "API", "MCP_HOST", "CACHE", "ASYNC_QUEUE", "NOSQL"):
        assert component_type in COMPONENT_ALERT_MAP


def test_strategy_is_swappable():
    """Verify the strategy can be swapped at runtime (core of Strategy pattern)."""
    ctx = AlertContext()
    ctx.set_strategy_for_component("CACHE")
    assert ctx.get_priority() == "P2"
    # Simulate escalation — swap to P0
    ctx.set_strategy_for_component("RDBMS")
    assert ctx.get_priority() == "P0"
