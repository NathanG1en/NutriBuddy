# tests/test_cache.py
"""Tests for high-performance SQLiteCache."""

import time
import pytest
from backend.services.cache import SQLiteCache


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_cache.db"
    return SQLiteCache(db_path=str(db_file), migrate_legacy=False)


def test_cache_set_and_get(temp_cache):
    temp_cache.set("apple", {"calories": 95, "name": "Apple"})
    result = temp_cache.get("apple")
    assert result is not None
    assert result["calories"] == 95
    assert result["name"] == "Apple"


def test_cache_miss(temp_cache):
    assert temp_cache.get("nonexistent_key") is None


def test_cache_ttl_expiration(temp_cache):
    temp_cache.set("short_lived", {"data": 123}, ttl_seconds=1)
    assert temp_cache.get("short_lived") == {"data": 123}
    time.sleep(1.1)
    assert temp_cache.get("short_lived") is None


def test_cache_delete_and_clear(temp_cache):
    temp_cache.set("k1", "v1")
    temp_cache.set("k2", "v2")
    assert temp_cache.has("k1")
    assert temp_cache.delete("k1") is True
    assert temp_cache.has("k1") is False

    temp_cache.clear()
    assert temp_cache.has("k2") is False


def test_cache_stats(temp_cache):
    temp_cache.set("item1", "val1")
    temp_cache.set("item2", "val2", ttl_seconds=1)
    stats = temp_cache.get_stats()
    assert stats["total_items"] == 2
