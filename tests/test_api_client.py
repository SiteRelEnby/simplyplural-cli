"""Tests for SimplyPluralAPI with mocked HTTP"""

import pytest
import json
from unittest.mock import patch, MagicMock

from simplyplural.api_client import SimplyPluralAPI, APIError
from tests.conftest import SYSTEM_ID


def make_response(status_code=200, json_data=None, text=""):
    """Helper to create a mock requests.Response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.text = text or json.dumps(json_data or {})
    resp.json.return_value = json_data
    resp.headers = {"Content-Type": "application/json"}
    return resp


class TestAPIClientInit:
    def test_sets_auth_header(self):
        api = SimplyPluralAPI("my-token")
        assert api.session.headers["Authorization"] == "my-token"

    def test_default_timeout(self):
        api = SimplyPluralAPI("tok")
        assert api.timeout == 10

    def test_config_overrides_timeout(self):
        config = MagicMock()
        config.api_timeout = 30
        config.max_retries = 5
        api = SimplyPluralAPI("tok", config_manager=config)
        assert api.timeout == 30
        assert api.max_retries == 5


class TestGetSystemId:
    def test_extracts_id_from_me(self):
        api = SimplyPluralAPI("tok")
        me_response = {
            "exists": True,
            "id": SYSTEM_ID,
            "content": {"uid": SYSTEM_ID, "username": "Test"},
        }
        with patch.object(api, '_request', return_value=me_response):
            result = api.get_system_id()
            assert result == SYSTEM_ID

    def test_caches_system_id(self):
        api = SimplyPluralAPI("tok")
        api._system_id = "cached-id"
        # Should return cached value without calling _request
        assert api.get_system_id() == "cached-id"

    def test_raises_on_missing_id(self):
        api = SimplyPluralAPI("tok")
        with patch.object(api, '_request', return_value={"exists": True}):
            with pytest.raises(APIError):
                api.get_system_id()


class TestGetFronters:
    def test_resolves_member_names(self):
        api = SimplyPluralAPI("tok")
        fronters = [
            {
                "exists": True,
                "id": "f1",
                "content": {"member": "m1", "custom": False, "live": True},
            }
        ]
        member_data = {"content": {"name": "Alice"}}

        with patch.object(api, '_request', return_value=fronters), \
             patch.object(api, 'get_member', return_value=member_data):
            result = api.get_fronters()
            assert result[0]["name"] == "Alice"
            assert result[0]["type"] == "member"

    def test_resolves_custom_front_names(self):
        api = SimplyPluralAPI("tok")
        fronters = [
            {
                "exists": True,
                "id": "f2",
                "content": {"member": "cf1", "custom": True, "live": True},
            }
        ]
        cf_data = {"content": {"name": "Blurry"}}

        with patch.object(api, '_request', return_value=fronters), \
             patch.object(api, 'get_custom_front', return_value=cf_data):
            result = api.get_fronters()
            assert result[0]["name"] == "Blurry"
            assert result[0]["type"] == "custom_front"

    def test_handles_api_error_gracefully(self):
        api = SimplyPluralAPI("tok")
        fronters = [
            {
                "exists": True,
                "id": "f1",
                "content": {"member": "m1", "custom": False, "live": True},
            }
        ]

        with patch.object(api, '_request', return_value=fronters), \
             patch.object(api, 'get_member', side_effect=APIError("not found")):
            result = api.get_fronters()
            # Should still return a result with fallback name
            assert len(result) == 1
            assert result[0]["type"] == "member"


class TestSensitiveDataRedaction:
    def test_auth_header_filtered(self):
        api = SimplyPluralAPI("secret-token")
        filtered = api._filter_sensitive_headers({"Authorization": "secret", "Content-Type": "json"})
        assert filtered["Authorization"] == "[REDACTED]"
        assert filtered["Content-Type"] == "json"
