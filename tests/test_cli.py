"""Tests for the CLI interface."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from fantasycalc_cli import __version__
from fantasycalc_cli.cli import _extract_row, app

runner = CliRunner()

SAMPLE_VALUES = [
    {
        "player": {
            "name": "Josh Allen",
            "position": "QB",
            "maybeTeam": "BUF",
            "age": 29,
            "id": 1,
            "fleaflickerId": 13761,
            "sleeperId": "4984",
            "espnId": 3918298,
            "mflId": "13589",
        },
        "value": 10358,
        "overallRank": 1,
        "positionRank": 1,
        "trend30Day": 50,
        "displayTrend": "UP",
    },
    {
        "player": {
            "name": "Bijan Robinson",
            "position": "RB",
            "maybeTeam": "ATL",
            "age": 23,
            "id": 2,
            "fleaflickerId": 17001,
        },
        "value": 9300,
        "overallRank": 3,
        "positionRank": 1,
        "trend30Day": -25,
        "displayTrend": "DOWN",
    },
]


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so assertions work in CI."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class DummyClient:
    def __init__(self, rows=None, source="api"):
        self.rows = rows if rows is not None else SAMPLE_VALUES
        self.source = source
        self.cache = self

    def fetch_values(self, **kwargs):
        return self.rows, self.source

    def clear(self):
        return 2


def make_client(rows=None, source="api"):
    return DummyClient(rows=rows, source=source)


# ------------------------------------------------------------------
# _extract_row
# ------------------------------------------------------------------


class TestExtractRow:
    def test_includes_platform_ids(self):
        row = SAMPLE_VALUES[0]
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
        output = strip_ansi(result.output)
        assert "FantasyCalc" in output
        assert "filters, sorting, cache, and export options" in output

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
        assert "--team" in output
        assert "--sort" in output
        assert "--cache-ttl" in output
        assert "--refresh-cache" in output
        assert "json" in output and "csv" in output

    def test_lookup_help(self):
        result = runner.invoke(app, ["lookup", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--name" in output
        assert "--exact" in output

    def test_export_help(self):
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--output" in output
        assert "--format" in output

    def test_index_help(self):
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--platform" in output
        assert "fleaflicker" in output

    def test_cache_help(self):
        result = runner.invoke(app, ["cache", "clear", "--help"])
        assert result.exit_code == 0
        assert "Delete local cached" in strip_ansi(result.output)

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


# ------------------------------------------------------------------
# CLI behavior
# ------------------------------------------------------------------


class TestCLIBehavior:
    def test_values_json_filter_sort_feedback(self, monkeypatch):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        result = runner.invoke(
            app,
            [
                "values",
                "--position",
                "QB",
                "--sort",
                "value",
                "--desc",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "Loaded 2 players from fresh API data." in output
        assert "Returning 1 players after filters and sorting by value." in output
        assert '"name": "Josh Allen"' in output
        assert '"name": "Bijan Robinson"' not in output

    def test_values_csv_output_to_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        output_file = tmp_path / "values.csv"
        result = runner.invoke(app, ["values", "--format", "csv", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        contents = output_file.read_text()
        assert "name,position,team,age,value" in contents
        assert "Josh Allen" in contents

    def test_lookup_exact(self, monkeypatch):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        result = runner.invoke(
            app,
            ["lookup", "--name", "Josh Allen", "--exact", "--format", "json"],
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "Found 1 matching players" in output
        assert '"name": "Josh Allen"' in output

    def test_lookup_no_match_has_guidance(self, monkeypatch):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        result = runner.invoke(app, ["lookup", "--name", "Nope", "--exact"])

        assert result.exit_code == 1
        assert "Try a broader search or omit --exact" in strip_ansi(result.output)

    def test_export_csv(self, monkeypatch, tmp_path):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        output_file = tmp_path / "export.csv"
        result = runner.invoke(app, ["export", "--output", str(output_file), "--format", "csv"])

        assert result.exit_code == 0
        assert "Saved 2 rows" in strip_ansi(result.output)
        assert "Josh Allen" in output_file.read_text()

    def test_index_stdout(self, monkeypatch):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        result = runner.invoke(app, ["index", "--platform", "fleaflicker"])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "Returning 2 indexed players for platform 'fleaflicker'." in output
        assert '"13761"' in output

    def test_cache_clear(self, monkeypatch):
        monkeypatch.setattr("fantasycalc_cli.cli._client", lambda: make_client())
        result = runner.invoke(app, ["cache", "clear"])

        assert result.exit_code == 0
        assert "Removed 2 cached file(s)." in strip_ansi(result.output)

    def test_invalid_ppr_is_rejected(self):
        result = runner.invoke(app, ["values", "--ppr", "0.25"])
        assert result.exit_code != 0
        assert "must be one of 0, 0.5, or 1" in strip_ansi(result.output)

    def test_invalid_num_qbs_is_rejected(self):
        result = runner.invoke(app, ["values", "--num-qbs", "3"])
        assert result.exit_code != 0
        assert "must be 1 or 2" in strip_ansi(result.output)
