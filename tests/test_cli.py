"""Tests for CLI argument parsing and command routing"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from simplyplural.cli import main, SimplyPluralCLI


def run_cli(*args):
    """Run the CLI with given args, capturing stdout/stderr"""
    with patch("sys.argv", ["sp"] + list(args)), \
         patch("sys.stdout", new_callable=StringIO) as stdout, \
         patch("sys.stderr", new_callable=StringIO) as stderr:
        try:
            code = main()
        except SystemExit as e:
            code = e.code
    return code, stdout.getvalue(), stderr.getvalue()


class TestCLIHelp:
    def test_no_args_shows_help(self):
        code, stdout, _ = run_cli()
        assert code == 1  # no command = error
        assert "usage:" in stdout.lower() or "usage:" in _.lower()

    def test_help_command(self):
        code, stdout, _ = run_cli("help")
        assert code == 0


class TestCLIArgParsing:
    def test_switch_requires_members(self):
        code, _, stderr = run_cli("switch")
        assert code != 0

    def test_daemon_requires_action(self):
        code, _, stderr = run_cli("daemon")
        assert code != 0

    def test_fronting_default_format(self):
        """Verify fronting command parses and tries to run"""
        # This will fail because there's no config, but it proves parsing works
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            code, _, _ = run_cli("fronting")
            instance.cmd_fronting.assert_called_once_with("text")

    def test_fronting_json_format(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            code, _, _ = run_cli("fronting", "--format=json")
            instance.cmd_fronting.assert_called_once_with("json")

    def test_who_alias(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("who")
            instance.cmd_fronting.assert_called_once()

    def test_w_alias(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("w")
            instance.cmd_fronting.assert_called_once()

    def test_switch_passes_members(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_switch.return_value = 0
            run_cli("switch", "Alice", "Bob")
            instance.cmd_switch.assert_called_once_with(["Alice", "Bob"], None, False)

    def test_switch_co_flag(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_switch.return_value = 0
            run_cli("switch", "--co", "Alice")
            instance.cmd_switch.assert_called_once_with(["Alice"], None, True)

    def test_daemon_start(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_daemon.return_value = 0
            run_cli("daemon", "start")
            instance.cmd_daemon.assert_called_once_with("start")

    def test_profile_flag(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("--profile", "alt", "fronting")
            MockCLI.assert_called_once_with("alt", False)

    def test_debug_flag(self):
        with patch("simplyplural.cli.SimplyPluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("--debug", "fronting")
            MockCLI.assert_called_once_with("default", True)


class TestAutoStartDaemon:
    def _make_cli(self, start_daemon=False, daemon_running=False):
        """Create a SimplyPluralCLI with mocked internals"""
        with patch.object(SimplyPluralCLI, '__init__', lambda self, *a, **k: None):
            cli = SimplyPluralCLI.__new__(SimplyPluralCLI)
        cli.config = MagicMock()
        cli.config.start_daemon = start_daemon
        cli.daemon_client = MagicMock()
        cli.daemon_client.is_running.return_value = daemon_running
        cli.profile = "default"
        cli.debug = False
        return cli

    @patch("simplyplural.cli.time.sleep")
    @patch("simplyplural.cli.subprocess.Popen")
    def test_auto_start_when_configured(self, mock_popen, _sleep):
        cli = self._make_cli(start_daemon=True, daemon_running=False)
        cli._maybe_auto_start_daemon()
        mock_popen.assert_called_once()

    @patch("simplyplural.cli.subprocess.Popen")
    def test_no_auto_start_when_disabled(self, mock_popen):
        cli = self._make_cli(start_daemon=False, daemon_running=False)
        cli._maybe_auto_start_daemon()
        mock_popen.assert_not_called()

    @patch("simplyplural.cli.subprocess.Popen")
    def test_no_auto_start_when_already_running(self, mock_popen):
        cli = self._make_cli(start_daemon=True, daemon_running=True)
        cli._maybe_auto_start_daemon()
        mock_popen.assert_not_called()


class TestCoFronting:
    def _make_cli(self):
        """Create a SimplyPluralCLI with mocked internals"""
        with patch.object(SimplyPluralCLI, '__init__', lambda self, *a, **k: None):
            cli = SimplyPluralCLI.__new__(SimplyPluralCLI)
        cli.config = MagicMock()
        cli.config.start_daemon = False
        cli.config.show_custom_front_indicators = False
        cli.daemon_client = MagicMock()
        cli.daemon_client.is_running.return_value = False
        cli.profile = "default"
        cli.debug = False
        cli.cache = MagicMock()
        cli.cache.invalidate_fronters = MagicMock()
        cli.api = MagicMock()
        cli.shell = MagicMock()
        return cli

    def test_co_adds_to_existing(self):
        cli = self._make_cli()
        # Current fronters: Alice
        cli.api.get_fronters.return_value = [
            {'name': 'Alice', 'type': 'member'}
        ]
        cli.api.register_switch.return_value = {}
        cli.cmd_switch(['Bob'], note=None, co=True)
        # Should register switch with both Alice and Bob
        cli.api.register_switch.assert_called_once_with(['Alice', 'Bob'], None)

    def test_co_multiple_members(self):
        cli = self._make_cli()
        # Current fronters: Alice
        cli.api.get_fronters.return_value = [
            {'name': 'Alice', 'type': 'member'}
        ]
        cli.api.register_switch.return_value = {}
        cli.cmd_switch(['Bob', 'Charlie'], note=None, co=True)
        # Should add both Bob and Charlie
        cli.api.register_switch.assert_called_once_with(
            ['Alice', 'Bob', 'Charlie'], None)

    def test_co_skips_already_fronting(self):
        cli = self._make_cli()
        cli.api.get_fronters.return_value = [
            {'name': 'Alice', 'type': 'member'}
        ]
        cli.api.register_switch.return_value = {}
        cli.cmd_switch(['Alice'], note=None, co=True)
        # Alice already fronting, list should just be Alice
        cli.api.register_switch.assert_called_once_with(['Alice'], None)

    def test_co_filters_unknown_names(self):
        cli = self._make_cli()
        # Simulate unresolved fronter
        cli.api.get_fronters.return_value = [
            {'name': 'Alice', 'type': 'member'},
            {'name': 'Unknown', 'type': 'member'},
        ]
        cli.api.register_switch.return_value = {}
        cli.cmd_switch(['Bob'], note=None, co=True)
        # Unknown should be filtered out
        cli.api.register_switch.assert_called_once_with(['Alice', 'Bob'], None)
