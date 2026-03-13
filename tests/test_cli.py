"""Tests for the CLI interface."""

from __future__ import annotations

from typer.testing import CliRunner

from fantasycalc_cli import __version__
from fantasycalc_cli.cli import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "FantasyCalc" in result.output

    def test_values_help(self):
        result = runner.invoke(app, ["values", "--help"])
        assert result.exit_code == 0
        assert "--dynasty" in result.output
        assert "--num-qbs" in result.output
        assert "--num-teams" in result.output
        assert "--ppr" in result.output
        assert "--limit" in result.output
        assert "--position" in result.output
        assert "--format" in result.output

    def test_lookup_help(self):
        result = runner.invoke(app, ["lookup", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output

    def test_export_help(self):
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
