"""Tests for the CLI interface."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from fantasycalc_cli import __version__
from fantasycalc_cli.cli import _extract_row, app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so assertions work in CI."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ------------------------------------------------------------------
# _extract_row
# ------------------------------------------------------------------


class TestExtractRow:
    def test_includes_platform_ids(self):
        row = {
            "player": {
                "name": "Josh Allen",
                "position": "QB",
                "maybeTeam": "BUF",
                "age": 29,
                "fleaflickerId": 13761,
                "sleeperId": "4984",
                "espnId": 3918298,
                "mflId": "13589",
            },
            "value": 10358,
            "overallRank": 1,
            "positionRank": 1,
        }
        result = _extract_row(row)
        assert result["fleaflickerId"] == "13761"
        assert result["sleeperId"] == "4984"
        assert result["espnId"] == "3918298"
        assert result["mflId"] == "13589"

    def test_missing_platform_ids_are_none(self):
        row = {
            "player": {"name": "Test Player", "position": "WR"},
            "value": 100,
        }
        result = _extract_row(row)
        assert result["fleaflickerId"] is None
        assert result["sleeperId"] is None
        assert result["espnId"] is None
        assert result["mflId"] is None
        assert result["yahooId"] is None

    def test_includes_trend_data(self):
        row = {
            "player": {"name": "Test", "position": "RB"},
            "value": 500,
            "trend30Day": 50,
            "displayTrend": "UP",
        }
        result = _extract_row(row)
        assert result["trend30Day"] == 50
        assert result["displayTrend"] == "UP"


# ------------------------------------------------------------------
# CLI help
# ------------------------------------------------------------------


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

    def test_index_help(self):
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--platform" in output

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
