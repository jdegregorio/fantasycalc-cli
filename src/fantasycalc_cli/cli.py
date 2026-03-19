"""Typer CLI for FantasyCalc dynasty valuations."""

from __future__ import annotations

import csv
import json
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from fantasycalc_cli import __version__
from fantasycalc_cli.client import (
    DEFAULT_CACHE_TTL,
    SUPPORTED_PLATFORMS,
    FantasyCalcClient,
    FantasyCalcClientError,
)

app = typer.Typer(
    name="fantasycalc",
    help=(
        "CLI for FantasyCalc dynasty fantasy football valuations. "
        "Use 'fantasycalc values --help' to discover filters, sorting, cache, and export options."
    ),
    no_args_is_help=True,
)
cache_app = typer.Typer(help="Manage local FantasyCalc cache files.")
app.add_typer(cache_app, name="cache")
console = Console()
err_console = Console(stderr=True)


# ------------------------------------------------------------------
# Shared types
# ------------------------------------------------------------------


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    csv = "csv"


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"


class SortField(str, Enum):
    value = "value"
    overall_rank = "overallRank"
    position_rank = "positionRank"
    name = "name"
    age = "age"
    team = "team"
    trend_30_day = "trend30Day"


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------


def _validate_num_qbs(value: int) -> int:
    if value not in {1, 2}:
        raise typer.BadParameter("must be 1 or 2 (2 = superflex)")
    return value


def _validate_num_teams(value: int) -> int:
    if value < 2 or value > 32:
        raise typer.BadParameter("must be between 2 and 32")
    return value


def _validate_limit(value: Optional[int]) -> Optional[int]:
    if value is None:
        return value
    if value < 1:
        raise typer.BadParameter("must be at least 1")
    return value


def _validate_ppr(value: float) -> float:
    if value not in {0, 0.5, 1}:
        raise typer.BadParameter("must be one of 0, 0.5, or 1")
    return value


def _validate_cache_ttl(value: int) -> int:
    if value < 0:
        raise typer.BadParameter("must be 0 or greater")
    return value


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client() -> FantasyCalcClient:
    return FantasyCalcClient()


def _extract_row(row: dict) -> dict:
    """Flatten a value row into a rich normalized dict.

    Includes platform IDs, trend data, and core valuation fields so
    downstream consumers can join across platforms without touching the
    raw API payload.
    """
    player = row.get("player") or {}
    result: dict = {
        "name": player.get("name", ""),
        "position": player.get("position", ""),
        "team": player.get("maybeTeam", ""),
        "age": player.get("age", ""),
        "value": row.get("value", 0),
        "overallRank": row.get("overallRank", ""),
        "positionRank": row.get("positionRank", ""),
        # Platform IDs — None when not available for a player
        "playerId": player.get("id"),
        "fleaflickerId": _str_or_none(player.get("fleaflickerId")),
        "sleeperId": _str_or_none(player.get("sleeperId")),
        "espnId": _str_or_none(player.get("espnId")),
        "mflId": _str_or_none(player.get("mflId")),
        "yahooId": _str_or_none(player.get("yahooId")),
        # Trend / extra metadata
        "trend30Day": row.get("trend30Day"),
        "displayTrend": row.get("displayTrend"),
    }
    return result


def _str_or_none(val) -> str | None:
    """Coerce a platform ID to string, or return None."""
    return str(val) if val is not None else None


def _rows_to_csv(rows: list[dict]) -> str:
    fieldnames = list(rows[0].keys()) if rows else [
        "name",
        "position",
        "team",
        "age",
        "value",
        "overallRank",
        "positionRank",
        "playerId",
        "fleaflickerId",
        "sleeperId",
        "espnId",
        "mflId",
        "yahooId",
        "trend30Day",
        "displayTrend",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _print_table(rows: list[dict], *, title: str = "FantasyCalc Values") -> None:
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Pos", justify="center")
    table.add_column("Team", justify="center")
    table.add_column("Age", justify="right")
    table.add_column("Value", justify="right", style="green")
    table.add_column("Trend", justify="right")
    table.add_column("Pos Rank", justify="right")

    for r in rows:
        table.add_row(
            str(r["overallRank"]),
            r["name"],
            r["position"],
            str(r["team"]),
            str(r["age"]),
            str(r["value"]),
            str(r["displayTrend"] or r["trend30Day"] or ""),
            str(r["positionRank"]),
        )
    console.print(table)


def _emit_rows(
    rows: list[dict],
    *,
    fmt: OutputFormat,
    output: Path | None = None,
    title: str = "FantasyCalc Values",
) -> None:
    if fmt == OutputFormat.json:
        payload = json.dumps(rows, indent=2)
    elif fmt == OutputFormat.csv:
        payload = _rows_to_csv(rows)
    else:
        payload = None

    if output is not None:
        if payload is None:
            output.write_text(json.dumps(rows, indent=2))
        else:
            output.write_text(payload)
        console.print(f"[green]Saved {len(rows)} rows to {output} ({fmt.value}).[/green]")
        return

    if fmt == OutputFormat.json:
        console.print_json(payload)
    elif fmt == OutputFormat.csv:
        console.print(payload, end="")
    else:
        _print_table(rows, title=title)


def _filter_rows(
    rows: list[dict],
    *,
    position: Position | None,
    team: str | None,
    min_value: int | None,
    max_value: int | None,
    age_min: int | None,
    age_max: int | None,
) -> list[dict]:
    filtered = rows
    if position is not None:
        filtered = [r for r in filtered if r["position"] == position.value]
    if team is not None:
        team_code = team.strip().upper()
        filtered = [r for r in filtered if str(r["team"]).upper() == team_code]
    if min_value is not None:
        filtered = [r for r in filtered if int(r["value"] or 0) >= min_value]
    if max_value is not None:
        filtered = [r for r in filtered if int(r["value"] or 0) <= max_value]
    if age_min is not None:
        filtered = [r for r in filtered if isinstance(r["age"], int) and r["age"] >= age_min]
    if age_max is not None:
        filtered = [r for r in filtered if isinstance(r["age"], int) and r["age"] <= age_max]
    return filtered


def _sort_rows(rows: list[dict], *, sort_by: SortField, desc: bool) -> list[dict]:
    def key(row: dict):
        value = row.get(sort_by.value)
        if value is None:
            return (1, "")
        return (0, value)

    return sorted(rows, key=key, reverse=desc)


def _describe_source(source: str, *, cache_ttl: int) -> str:
    if source == "api":
        return "fresh API data"
    if source == "cache":
        return f"cached data (<= {cache_ttl}s old)"
    if source == "stale-cache":
        return "stale cached data because the API request failed"
    return source


def _load_values(
    *,
    dynasty: bool,
    num_qbs: int,
    num_teams: int,
    ppr: float,
    cache_ttl: int,
    use_cache: bool,
    refresh_cache: bool,
) -> tuple[list[dict], str]:
    client = _client()
    try:
        raw, source = client.fetch_values(
            is_dynasty=dynasty,
            num_qbs=num_qbs,
            num_teams=num_teams,
            ppr=ppr,
            cache_ttl=cache_ttl,
            use_cache=use_cache,
            refresh_cache=refresh_cache,
        )
    except FantasyCalcClientError as exc:
        err_console.print(f"[red]Error fetching values:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    return raw, source


def _feedback_summary(*, rows: list[dict], source: str, cache_ttl: int) -> None:
    console.print(
        "[cyan]Loaded "
        f"{len(rows)} players from {_describe_source(source, cache_ttl=cache_ttl)}."
        "[/cyan]"
    )


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"fantasycalc-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-v",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """FantasyCalc CLI - Dynasty fantasy football valuations."""


@app.command()
def values(
    dynasty: Annotated[
        bool,
        typer.Option(
            "--dynasty/--redraft",
            help="Choose dynasty or redraft values. Defaults to dynasty.",
        ),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option(
            "--num-qbs",
            callback=lambda ctx, param, value: _validate_num_qbs(value),
            help="Number of starting QBs. Use 2 for superflex or 1 for 1QB.",
        ),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option(
            "--num-teams",
            callback=lambda ctx, param, value: _validate_num_teams(value),
            help="League size. Must be between 2 and 32.",
        ),
    ] = 12,
    ppr: Annotated[
        float,
        typer.Option(
            "--ppr",
            callback=lambda ctx, param, value: _validate_ppr(value),
            help="Points per reception. Supported values: 0, 0.5, 1.",
        ),
    ] = 1,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit",
            callback=lambda ctx, param, value: _validate_limit(value),
            help="Number of rows to display after filtering. Omit to show all rows.",
        ),
    ] = 50,
    position: Annotated[
        Optional[Position],
        typer.Option("--position", "-p", help="Filter to a single position."),
    ] = None,
    team: Annotated[
        Optional[str],
        typer.Option("--team", help="Filter to an NFL team abbreviation, e.g. BUF."),
    ] = None,
    min_value: Annotated[
        Optional[int],
        typer.Option("--min-value", help="Only include players at or above this value."),
    ] = None,
    max_value: Annotated[
        Optional[int],
        typer.Option("--max-value", help="Only include players at or below this value."),
    ] = None,
    age_min: Annotated[
        Optional[int],
        typer.Option("--age-min", help="Only include players this age or older."),
    ] = None,
    age_max: Annotated[
        Optional[int],
        typer.Option("--age-max", help="Only include players this age or younger."),
    ] = None,
    sort_by: Annotated[
        SortField,
        typer.Option(
            "--sort",
            help="Sort field. Useful choices: value, trend30Day, name, age, overallRank.",
        ),
    ] = SortField.overall_rank,
    desc: Annotated[
        bool,
        typer.Option("--desc/--asc", help="Sort descending or ascending."),
    ] = False,
    fmt: Annotated[
        OutputFormat,
        typer.Option(
            "--format", "-f", help="Output format: table, json, or csv.",
        ),
    ] = OutputFormat.table,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output", "-o", help="Write table-equivalent JSON/CSV output to a file.",
        ),
    ] = None,
    cache_ttl: Annotated[
        int,
        typer.Option(
            "--cache-ttl",
            callback=lambda ctx, param, value: _validate_cache_ttl(value),
            help=(
                "Reuse cached values newer than this many seconds. "
                f"Default: {DEFAULT_CACHE_TTL}."
            ),
        ),
    ] = DEFAULT_CACHE_TTL,
    use_cache: Annotated[
        bool,
        typer.Option(
            "--use-cache/--no-cache",
            help="Enable or disable local cache reads/writes for this command.",
        ),
    ] = True,
    refresh_cache: Annotated[
        bool,
        typer.Option(
            "--refresh-cache",
            help="Bypass cache reads and fetch fresh API data before updating the cache.",
        ),
    ] = False,
) -> None:
    """Fetch, filter, sort, and display current FantasyCalc values."""
    raw, source = _load_values(
        dynasty=dynasty,
        num_qbs=num_qbs,
        num_teams=num_teams,
        ppr=ppr,
        cache_ttl=cache_ttl,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
    )

    rows = [_extract_row(r) for r in raw]
    _feedback_summary(rows=rows, source=source, cache_ttl=cache_ttl)

    rows = _filter_rows(
        rows,
        position=position,
        team=team,
        min_value=min_value,
        max_value=max_value,
        age_min=age_min,
        age_max=age_max,
    )
    rows = _sort_rows(rows, sort_by=sort_by, desc=desc)
    if limit is not None:
        rows = rows[:limit]

    console.print(
        "[cyan]Returning "
        f"{len(rows)} players after filters and sorting by {sort_by.value}."
        "[/cyan]"
    )
    _emit_rows(rows, fmt=fmt, output=output, title="FantasyCalc Values")


@app.command()
def lookup(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Player name to search for."),
    ],
    exact: Annotated[
        bool,
        typer.Option(
            "--exact",
            help="Require an exact case-insensitive name match instead of substring matching.",
        ),
    ] = False,
    dynasty: Annotated[
        bool,
        typer.Option("--dynasty/--redraft", help="Choose dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option(
            "--num-qbs",
            callback=lambda ctx, param, value: _validate_num_qbs(value),
            help="Number of starting QBs. Use 2 for superflex or 1 for 1QB.",
        ),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option(
            "--num-teams",
            callback=lambda ctx, param, value: _validate_num_teams(value),
            help="League size. Must be between 2 and 32.",
        ),
    ] = 12,
    ppr: Annotated[
        float,
        typer.Option(
            "--ppr",
            callback=lambda ctx, param, value: _validate_ppr(value),
            help="Points per reception. Supported values: 0, 0.5, 1.",
        ),
    ] = 1,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format: table, json, or csv."),
    ] = OutputFormat.table,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write results to a JSON or CSV file."),
    ] = None,
    cache_ttl: Annotated[
        int,
        typer.Option(
            "--cache-ttl",
            callback=lambda ctx, param, value: _validate_cache_ttl(value),
            help=f"Reuse cached values newer than this many seconds. Default: {DEFAULT_CACHE_TTL}.",
        ),
    ] = DEFAULT_CACHE_TTL,
    use_cache: Annotated[
        bool,
        typer.Option("--use-cache/--no-cache", help="Enable or disable local cache usage."),
    ] = True,
    refresh_cache: Annotated[
        bool,
        typer.Option("--refresh-cache", help="Force a fresh API request before searching."),
    ] = False,
) -> None:
    """Search for one or more players by name."""
    raw, source = _load_values(
        dynasty=dynasty,
        num_qbs=num_qbs,
        num_teams=num_teams,
        ppr=ppr,
        cache_ttl=cache_ttl,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
    )
    _feedback_summary(rows=raw, source=source, cache_ttl=cache_ttl)

    matches = FantasyCalcClient.search_player(name, raw, exact=exact)
    if not matches:
        err_console.print(
            "[yellow]No players found matching "
            f"'{name}'. Try a broader search or omit --exact.[/yellow]"
        )
        raise typer.Exit(code=1)

    rows = [_extract_row(r) for r in matches]
    console.print(f"[cyan]Found {len(rows)} matching players for '{name}'.[/cyan]")
    _emit_rows(rows, fmt=fmt, output=output, title=f"Matches for {name}")


@app.command()
def export(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path."),
    ],
    dynasty: Annotated[
        bool,
        typer.Option("--dynasty/--redraft", help="Choose dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option(
            "--num-qbs",
            callback=lambda ctx, param, value: _validate_num_qbs(value),
            help="Number of starting QBs. Use 2 for superflex or 1 for 1QB.",
        ),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option(
            "--num-teams",
            callback=lambda ctx, param, value: _validate_num_teams(value),
            help="League size. Must be between 2 and 32.",
        ),
    ] = 12,
    ppr: Annotated[
        float,
        typer.Option(
            "--ppr",
            callback=lambda ctx, param, value: _validate_ppr(value),
            help="Points per reception. Supported values: 0, 0.5, 1.",
        ),
    ] = 1,
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            help="Export format. Use json for raw-ish normalized records or csv for spreadsheets.",
        ),
    ] = OutputFormat.json,
    cache_ttl: Annotated[
        int,
        typer.Option(
            "--cache-ttl",
            callback=lambda ctx, param, value: _validate_cache_ttl(value),
            help=f"Reuse cached values newer than this many seconds. Default: {DEFAULT_CACHE_TTL}.",
        ),
    ] = DEFAULT_CACHE_TTL,
    use_cache: Annotated[
        bool,
        typer.Option("--use-cache/--no-cache", help="Enable or disable local cache usage."),
    ] = True,
    refresh_cache: Annotated[
        bool,
        typer.Option("--refresh-cache", help="Force a fresh API request before exporting."),
    ] = False,
) -> None:
    """Export full player values to JSON or CSV."""
    raw, source = _load_values(
        dynasty=dynasty,
        num_qbs=num_qbs,
        num_teams=num_teams,
        ppr=ppr,
        cache_ttl=cache_ttl,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
    )
    rows = [_extract_row(r) for r in raw]
    _feedback_summary(rows=rows, source=source, cache_ttl=cache_ttl)
    _emit_rows(rows, fmt=format, output=output, title="FantasyCalc Export")


@app.command()
def index(
    platform: Annotated[
        str,
        typer.Option(
            "--platform",
            help=(
                "Platform to key by for cross-platform joins. Supported: "
                f"{', '.join(SUPPORTED_PLATFORMS)}."
            ),
        ),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file path (default: stdout)."),
    ] = None,
    dynasty: Annotated[
        bool,
        typer.Option("--dynasty/--redraft", help="Choose dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option(
            "--num-qbs",
            callback=lambda ctx, param, value: _validate_num_qbs(value),
            help="Number of starting QBs. Use 2 for superflex or 1 for 1QB.",
        ),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option(
            "--num-teams",
            callback=lambda ctx, param, value: _validate_num_teams(value),
            help="League size. Must be between 2 and 32.",
        ),
    ] = 12,
    ppr: Annotated[
        float,
        typer.Option(
            "--ppr",
            callback=lambda ctx, param, value: _validate_ppr(value),
            help="Points per reception. Supported values: 0, 0.5, 1.",
        ),
    ] = 1,
    cache_ttl: Annotated[
        int,
        typer.Option(
            "--cache-ttl",
            callback=lambda ctx, param, value: _validate_cache_ttl(value),
            help=f"Reuse cached values newer than this many seconds. Default: {DEFAULT_CACHE_TTL}.",
        ),
    ] = DEFAULT_CACHE_TTL,
    use_cache: Annotated[
        bool,
        typer.Option("--use-cache/--no-cache", help="Enable or disable local cache usage."),
    ] = True,
    refresh_cache: Annotated[
        bool,
        typer.Option("--refresh-cache", help="Force a fresh API request before indexing."),
    ] = False,
) -> None:
    """Export values as a platform-ID-keyed JSON mapping for cross-platform joins."""
    raw, source = _load_values(
        dynasty=dynasty,
        num_qbs=num_qbs,
        num_teams=num_teams,
        ppr=ppr,
        cache_ttl=cache_ttl,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
    )
    _feedback_summary(rows=raw, source=source, cache_ttl=cache_ttl)

    try:
        raw_index = FantasyCalcClient.build_platform_index(raw, platform=platform)
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    normalized = {pid: _extract_row(row) for pid, row in raw_index.items()}
    payload = json.dumps(normalized, indent=2)
    if output is not None:
        output.write_text(payload)
        console.print(
            "[green]Saved "
            f"{len(normalized)} indexed players for platform '{platform}' to {output}."
            "[/green]"
        )
    else:
        console.print(
            f"[cyan]Returning {len(normalized)} indexed players for platform '{platform}'.[/cyan]",
        )
        console.print_json(payload)


@cache_app.command("clear")
def cache_clear() -> None:
    """Delete local cached FantasyCalc responses."""
    removed = _client().cache.clear()
    console.print(f"[green]Removed {removed} cached file(s).[/green]")


if __name__ == "__main__":
    app()
