"""Tests for DaemonState initialization and update handling"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from simplyplural.daemon import DaemonState
from tests.conftest import MOCK_FRONTERS, MOCK_MEMBERS, MOCK_CUSTOM_FRONTS


@pytest.fixture
def state():
    return DaemonState(debug=False)


@pytest.fixture
def state_with_mock_api(mock_api):
    mock_cache = MagicMock()
    mock_cache.get_fronters.return_value = None
    mock_cache.get_members.return_value = None
    mock_cache.get_custom_fronts.return_value = None
    return DaemonState(api_client=mock_api, cache_manager=mock_cache, debug=False)


class TestDaemonStateInit:
    async def test_initialize_from_api(self, state_with_mock_api, mock_api):
        await state_with_mock_api.initialize()
        assert state_with_mock_api.current_fronters == MOCK_FRONTERS
        assert len(state_with_mock_api.members) == 2
        assert len(state_with_mock_api.custom_fronts) == 1

    async def test_front_history_seeded_on_init(self, state_with_mock_api):
        await state_with_mock_api.initialize()
        assert len(state_with_mock_api.front_history) == 1
        assert "front001" in state_with_mock_api.front_history
        assert state_with_mock_api.last_update_times["front_history"] > 0

    async def test_initialize_no_api_no_cache(self, state):
        await state.initialize()
        assert state.current_fronters is None
        assert state.members == {}
        assert state.custom_fronts == {}


class TestDaemonStateUpdates:
    async def test_front_history_insert(self, state):
        # Seed with initial fronter
        state.front_history["front001"] = {
            "member": "m1", "live": True, "startTime": 1000
        }
        state.current_fronters = [state.front_history["front001"]]

        # New fronter arrives via WebSocket
        new_content = {"member": "m2", "live": True, "startTime": 2000}
        await state.handle_update("frontHistory", "insert", "front002", new_content)

        assert len(state.current_fronters) == 2
        # Most recent first
        assert state.current_fronters[0]["startTime"] == 2000

    async def test_front_history_delete(self, state):
        state.front_history["front001"] = {
            "member": "m1", "live": True, "startTime": 1000
        }

        await state.handle_update("frontHistory", "delete", "front001", {})
        assert "front001" not in state.front_history
        assert len(state.current_fronters) == 0

    async def test_member_insert(self, state):
        content = {"name": "Charlie", "pronouns": "they/them"}
        await state.handle_update("members", "insert", "m3", content)
        assert "m3" in state.members
        assert state.members["m3"]["name"] == "Charlie"

    async def test_member_delete(self, state):
        state.members["m1"] = {"name": "Alice"}
        await state.handle_update("members", "delete", "m1", {})
        assert "m1" not in state.members

    async def test_custom_front_insert(self, state):
        content = {"name": "Foggy", "desc": "brain fog"}
        await state.handle_update("customFronts", "insert", "cf2", content)
        assert "cf2" in state.custom_fronts

    async def test_custom_front_delete(self, state):
        state.custom_fronts["cf1"] = {"name": "Blurry"}
        await state.handle_update("customFronts", "delete", "cf1", {})
        assert "cf1" not in state.custom_fronts

    async def test_update_count_increments(self, state):
        assert state.update_count == 0
        await state.handle_update("members", "insert", "m1", {"name": "X"})
        assert state.update_count == 1
        await state.handle_update("members", "update", "m1", {"name": "Y"})
        assert state.update_count == 2


class TestDaemonStateQueries:
    def test_get_fronters_empty(self, state):
        result = state.get_fronters()
        assert result["fronters"] == []

    def test_get_members_empty(self, state):
        result = state.get_members()
        assert result["members"] == []

    def test_get_status(self, state):
        status = state.get_status()
        assert "uptime" in status
        assert status["fronters_count"] == 0
        assert status["members_count"] == 0
