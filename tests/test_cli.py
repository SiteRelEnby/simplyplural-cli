"""Tests for CLI argument parsing and command routing"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from simplyplural.cli import main


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
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            code, _, _ = run_cli("fronting")
            instance.cmd_fronting.assert_called_once_with("human")

    def test_fronting_json_format(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            code, _, _ = run_cli("fronting", "--format=json")
            instance.cmd_fronting.assert_called_once_with("json")

    def test_who_alias(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("who")
            instance.cmd_fronting.assert_called_once()

    def test_w_alias(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("w")
            instance.cmd_fronting.assert_called_once()

    def test_switch_passes_members(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_switch.return_value = 0
            run_cli("switch", "Alice", "Bob")
            instance.cmd_switch.assert_called_once_with(["Alice", "Bob"], None, False)

    def test_switch_co_flag(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_switch.return_value = 0
            run_cli("switch", "--co", "Alice")
            instance.cmd_switch.assert_called_once_with(["Alice"], None, True)

    def test_daemon_start(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_daemon.return_value = 0
            run_cli("daemon", "start")
            instance.cmd_daemon.assert_called_once_with("start")

    def test_profile_flag(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("--profile", "alt", "fronting")
            MockCLI.assert_called_once_with("alt", False)

    def test_debug_flag(self):
        with patch("simplyplural.cli.SimplePluralCLI") as MockCLI:
            instance = MockCLI.return_value
            instance.cmd_fronting.return_value = 0
            run_cli("--debug", "fronting")
            MockCLI.assert_called_once_with("default", True)
