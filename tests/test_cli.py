"""Tests for the CLI interface."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from fantasycalc_cli import __version__
from fantasycalc_cli.cli import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so assertions work in CI."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "FantasyCalc" in result.output

    def test_values_help(self):
        result = runner.invoke(app, ["values", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--dynasty" in output
        assert "--num-qbs" in output
        assert "--num-teams" in output
        assert "--ppr" in output
        assert "--limit" in output
        assert "--position" in output
        assert "--format" in output

    def test_lookup_help(self):
        result = runner.invoke(app, ["lookup", "--help"])
        assert result.exit_code == 0
        assert "--name" in strip_ansi(result.output)

    def test_export_help(self):
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "--output" in strip_ansi(result.output)

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
