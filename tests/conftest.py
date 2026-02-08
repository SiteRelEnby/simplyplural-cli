"""Shared test fixtures for Simply Plural CLI tests"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# -- Mock API response data --

SYSTEM_ID = "abc123systemid"

MOCK_FRONTERS = [
    {
        "exists": True,
        "id": "front001",
        "content": {
            "member": "member001",
            "startTime": 1700000000000,
            "live": True,
            "custom": False,
            "customStatus": "",
            "uid": SYSTEM_ID,
            "lastOperationTime": 1700000000100,
        },
        "name": "Alice",
        "type": "member",
    }
]

MOCK_MEMBERS = [
    {
        "exists": True,
        "id": "member001",
        "content": {
            "name": "Alice",
            "pronouns": "she/her",
            "desc": "",
            "uid": SYSTEM_ID,
            "color": "#ff0000",
        },
    },
    {
        "exists": True,
        "id": "member002",
        "content": {
            "name": "Bob",
            "pronouns": "he/him",
            "desc": "",
            "uid": SYSTEM_ID,
            "color": "#0000ff",
        },
    },
]

MOCK_CUSTOM_FRONTS = [
    {
        "exists": True,
        "id": "cf001",
        "content": {
            "name": "Blurry",
            "desc": "When nobody is clearly fronting",
            "uid": SYSTEM_ID,
            "color": "#888888",
        },
    }
]

MOCK_ME_RESPONSE = {
    "exists": True,
    "id": SYSTEM_ID,
    "content": {
        "uid": SYSTEM_ID,
        "isAsystem": True,
        "username": "TestSystem",
    },
}


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Temporary config directory"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def sample_config(tmp_config_dir):
    """Write a sample config file and return its path"""
    config_file = tmp_config_dir / "simplyplural.conf"
    config_file.write_text(
        '[default]\n'
        'api_token = "test-token-abc123"\n'
        'default_output_format = "text"\n'
        'show_custom_front_indicators = true\n'
        'custom_front_indicator_style = "character"\n'
        'custom_front_indicator_character = "^"\n'
    )
    return config_file


@pytest.fixture
def mock_api():
    """A mock SimplyPluralAPI that returns test data without network calls"""
    api = MagicMock()
    api.api_token = "test-token-abc123"
    api.debug = False
    api.get_fronters.return_value = MOCK_FRONTERS
    api.get_members.return_value = MOCK_MEMBERS
    api.get_custom_fronts.return_value = MOCK_CUSTOM_FRONTS
    api.get_system_id.return_value = SYSTEM_ID
    return api
