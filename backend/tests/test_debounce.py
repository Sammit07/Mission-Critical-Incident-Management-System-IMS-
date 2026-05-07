"""
Unit tests for the debounce logic in IngestionService.

Key correctness property: concurrent calls to _get_or_create_work_item_id
for the same component_id must return exactly one is_new=True, regardless
of how many callers race simultaneously.
"""
import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from app.services.ingestion_service import IngestionService


def _make_atomic_redis():
    """Returns a mock Redis client that faithfully emulates SET NX atomicity."""
    stored: dict[str, str] = {}
    lock = asyncio.Lock()

    async def fake_set(key, value, nx=False, ex=None):
        async with lock:
            if nx and key in stored:
                return False
            stored[key] = value
            return True

    async def fake_get(key):
        return stored.get(key)

    mock = AsyncMock()
    mock.set = fake_set
    mock.get = fake_get
    return mock


@pytest.mark.asyncio
async def test_debounce_concurrent_same_component_returns_one_new():
    """10 concurrent calls for the same component → exactly one is_new=True."""
    mock_redis = _make_atomic_redis()

    with patch("app.services.ingestion_service.get_redis", return_value=mock_redis):
        service = IngestionService()
        results = await asyncio.gather(*[
            service._get_or_create_work_item_id("DB_PRIMARY_01", f"tentative-{i}")
            for i in range(10)
        ])

    new_flags = [is_new for _, is_new in results]
    assert sum(new_flags) == 1, f"Expected exactly 1 is_new=True, got {sum(new_flags)}"


@pytest.mark.asyncio
async def test_debounce_different_components_each_new():
    """Each unique component_id gets its own is_new=True."""
    mock_redis = _make_atomic_redis()

    with patch("app.services.ingestion_service.get_redis", return_value=mock_redis):
        service = IngestionService()
        results = await asyncio.gather(*[
            service._get_or_create_work_item_id(f"COMPONENT_{i}", f"tentative-{i}")
            for i in range(5)
        ])

    new_flags = [is_new for _, is_new in results]
    assert all(new_flags), "Every distinct component should be new"


@pytest.mark.asyncio
async def test_debounce_existing_key_returns_same_id():
    """When the debounce key already exists, the stored work_item_id is returned."""
    stored_id = "existing-work-item-uuid"
    mock_redis = _make_atomic_redis()
    # Pre-seed as if another worker already claimed this component
    await mock_redis.set("debounce:API_GW_01", stored_id, nx=True, ex=10)

    with patch("app.services.ingestion_service.get_redis", return_value=mock_redis):
        service = IngestionService()
        work_item_id, is_new = await service._get_or_create_work_item_id(
            "API_GW_01", "new-tentative-id"
        )

    assert is_new is False
    assert work_item_id == stored_id
