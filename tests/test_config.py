"""Tests for ConfigManager"""

import pytest
from unittest.mock import patch
from pathlib import Path

from simplyplural.config_manager import ConfigManager


@pytest.fixture
def config_with_dir(tmp_path):
    """Create a ConfigManager pointing at a temp directory"""
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    config_dir.mkdir()
    cache_dir.mkdir()

    config_file = config_dir / "simplyplural.conf"
    config_file.write_text(
        '[default]\n'
        'api_token = "test-token"\n'
        'default_output_format = "text"\n'
    )

    with patch.object(ConfigManager, '_get_config_dir', return_value=config_dir), \
         patch.object(ConfigManager, '_get_cache_dir', return_value=cache_dir):
        return ConfigManager("default")


class TestConfigManager:
    def test_loads_token(self, config_with_dir):
        assert config_with_dir.api_token == "test-token"

    def test_default_output_format(self, config_with_dir):
        assert config_with_dir.default_output_format == "text"

    def test_is_configured(self, config_with_dir):
        assert config_with_dir.is_configured()

    def test_not_configured_without_token(self, tmp_path):
        config_dir = tmp_path / "config"
        cache_dir = tmp_path / "cache"
        config_dir.mkdir()
        cache_dir.mkdir()

        config_file = config_dir / "simplyplural.conf"
        config_file.write_text('[default]\napi_token = ""\n')

        with patch.object(ConfigManager, '_get_config_dir', return_value=config_dir), \
             patch.object(ConfigManager, '_get_cache_dir', return_value=cache_dir):
            cfg = ConfigManager("default")
            assert not cfg.is_configured()

    def test_list_profiles(self, tmp_path):
        config_dir = tmp_path / "config"
        cache_dir = tmp_path / "cache"
        config_dir.mkdir()
        cache_dir.mkdir()

        config_file = config_dir / "simplyplural.conf"
        config_file.write_text(
            '[default]\napi_token = "tok1"\n\n'
            '[second]\napi_token = "tok2"\n'
        )

        with patch.object(ConfigManager, '_get_config_dir', return_value=config_dir), \
             patch.object(ConfigManager, '_get_cache_dir', return_value=cache_dir):
            cfg = ConfigManager("default")
            profiles = cfg.list_profiles()
            assert "default" in profiles
            assert "second" in profiles

    def test_profile_cache_dirs_are_isolated(self, tmp_path):
        config_dir = tmp_path / "config"
        cache_dir = tmp_path / "cache"
        config_dir.mkdir()
        cache_dir.mkdir()

        config_file = config_dir / "simplyplural.conf"
        config_file.write_text(
            '[default]\napi_token = "tok1"\n\n'
            '[other]\napi_token = "tok2"\n'
        )

        with patch.object(ConfigManager, '_get_config_dir', return_value=config_dir), \
             patch.object(ConfigManager, '_get_cache_dir', return_value=cache_dir):
            cfg1 = ConfigManager("default")
            cfg2 = ConfigManager("other")
            dir1 = cfg1.get_profile_cache_dir()
            dir2 = cfg2.get_profile_cache_dir()
            assert dir1 != dir2

    def test_default_cache_ttls(self, config_with_dir):
        assert config_with_dir.cache_fronters_ttl == 900
        assert config_with_dir.cache_members_ttl == 3600

    def test_start_daemon_defaults_true(self, config_with_dir):
        assert config_with_dir.start_daemon is True
