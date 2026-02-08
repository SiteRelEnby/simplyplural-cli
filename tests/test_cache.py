"""Tests for CacheManager"""

import time
import pytest
from unittest.mock import MagicMock

from simplyplural.cache_manager import CacheManager


@pytest.fixture
def cache(tmp_cache_dir):
    """Create a CacheManager with temp directory and default TTLs"""
    config = MagicMock()
    config.cache_fronters_ttl = 900
    config.cache_members_ttl = 3600
    config.cache_switches_ttl = 1800
    config.cache_custom_fronts_ttl = 3600
    return CacheManager(str(tmp_cache_dir), config)


class TestCacheManager:
    def test_set_and_get_fronters(self, cache):
        data = [{"id": "f1", "name": "Alice"}]
        cache.set_fronters(data)
        result = cache.get_fronters()
        assert result is not None
        assert result[0]["name"] == "Alice"

    def test_set_and_get_members(self, cache):
        data = [{"id": "m1", "content": {"name": "Bob"}}]
        cache.set_members(data)
        result = cache.get_members()
        assert result is not None
        assert len(result) == 1

    def test_set_and_get_custom_fronts(self, cache):
        data = [{"id": "cf1", "content": {"name": "Blurry"}}]
        cache.set_custom_fronts(data)
        result = cache.get_custom_fronts()
        assert result is not None
        assert result[0]["id"] == "cf1"

    def test_individual_member_set_and_invalidate(self, cache):
        cache.set_member("m1", {"content": {"name": "Alice"}})
        cache.invalidate_member("m1")
        # Individual invalidation shouldn't crash

    def test_individual_custom_front_set_and_invalidate(self, cache):
        cache.set_custom_front("cf1", {"content": {"name": "Blurry"}})
        cache.invalidate_custom_front("cf1")

    def test_get_returns_none_when_empty(self, cache):
        assert cache.get_fronters() is None

    def test_cache_persists_to_disk(self, tmp_cache_dir):
        """Verify cache survives a new CacheManager instance"""
        config = MagicMock()
        config.cache_fronters_ttl = 900
        config.cache_members_ttl = 3600
        config.cache_switches_ttl = 1800
        config.cache_custom_fronts_ttl = 3600

        cache1 = CacheManager(str(tmp_cache_dir), config)
        cache1.set_fronters([{"id": "f1", "name": "Alice"}])

        cache2 = CacheManager(str(tmp_cache_dir), config)
        result = cache2.get_fronters()
        assert result is not None
        assert result[0]["name"] == "Alice"
