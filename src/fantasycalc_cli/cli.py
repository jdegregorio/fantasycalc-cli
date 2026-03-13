"""Typer CLI for FantasyCalc dynasty valuations."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from fantasycalc_cli import __version__
from fantasycalc_cli.client import FantasyCalcClient

app = typer.Typer(
    name="fantasycalc",
    help="CLI for FantasyCalc dynasty fantasy football valuations.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


# ------------------------------------------------------------------
# Shared types
# ------------------------------------------------------------------


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client() -> FantasyCalcClient:
    return FantasyCalcClient()


def _extract_row(row: dict) -> dict:
    """Flatten a value row into a simple dict for display."""
    player = row.get("player") or {}
    return {
        "name": player.get("name", ""),
        "position": player.get("position", ""),
        "team": player.get("maybeTeam", ""),
        "age": player.get("age", ""),
        "value": row.get("value", 0),
        "overallRank": row.get("overallRank", ""),
        "positionRank": row.get("positionRank", ""),
    }


def _print_table(rows: list[dict]) -> None:
    table = Table(title="FantasyCalc Values", show_lines=False)
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Pos", justify="center")
    table.add_column("Team", justify="center")
    table.add_column("Age", justify="right")
    table.add_column("Value", justify="right", style="green")
    table.add_column("Pos Rank", justify="right")

    for r in rows:
        table.add_row(
            str(r["overallRank"]),
            r["name"],
            r["position"],
            str(r["team"]),
            str(r["age"]),
            str(r["value"]),
            str(r["positionRank"]),
        )
    console.print(table)


def _print_json(rows: list[dict]) -> None:
    console.print_json(json.dumps(rows))


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
        typer.Option("--dynasty/--redraft", help="Dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option("--num-qbs", help="Number of starting QBs (2 = superflex)."),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option("--num-teams", help="League size."),
    ] = 12,
    ppr: Annotated[
        int,
        typer.Option("--ppr", help="Points per reception (0, 0.5, or 1)."),
    ] = 1,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Number of rows to display."),
    ] = 50,
    position: Annotated[
        Optional[Position],
        typer.Option("--position", "-p", help="Filter by position."),
    ] = None,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.table,
) -> None:
    """Fetch and display current dynasty player values."""
    client = _client()
    try:
        raw = client.fetch_values(
            is_dynasty=dynasty, num_qbs=num_qbs, num_teams=num_teams, ppr=ppr,
        )
    except Exception as exc:
        err_console.print(f"[red]Error fetching values:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    rows = [_extract_row(r) for r in raw]

    if position is not None:
        rows = [r for r in rows if r["position"] == position.value]

    rows = rows[:limit]

    if fmt == OutputFormat.json:
        _print_json(rows)
    else:
        _print_table(rows)


@app.command()
def lookup(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Player name to search for."),
    ],
    dynasty: Annotated[
        bool,
        typer.Option("--dynasty/--redraft", help="Dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option("--num-qbs", help="Number of starting QBs."),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option("--num-teams", help="League size."),
    ] = 12,
    ppr: Annotated[
        int,
        typer.Option("--ppr", help="Points per reception."),
    ] = 1,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.table,
) -> None:
    """Search for a player by name."""
    client = _client()
    try:
        raw = client.fetch_values(
            is_dynasty=dynasty, num_qbs=num_qbs, num_teams=num_teams, ppr=ppr,
        )
    except Exception as exc:
        err_console.print(f"[red]Error fetching values:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    matches = client.search_player(name, raw)
    if not matches:
        err_console.print(
            f"[yellow]No players found matching '{name}'.[/yellow]",
        )
        raise typer.Exit(code=1)

    rows = [_extract_row(r) for r in matches]

    if fmt == OutputFormat.json:
        _print_json(rows)
    else:
        _print_table(rows)


@app.command()
def export(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path."),
    ],
    dynasty: Annotated[
        bool,
        typer.Option("--dynasty/--redraft", help="Dynasty or redraft values."),
    ] = True,
    num_qbs: Annotated[
        int,
        typer.Option("--num-qbs", help="Number of starting QBs."),
    ] = 2,
    num_teams: Annotated[
        int,
        typer.Option("--num-teams", help="League size."),
    ] = 12,
    ppr: Annotated[
        int,
        typer.Option("--ppr", help="Points per reception."),
    ] = 1,
) -> None:
    """Export full player values to a JSON file."""
    client = _client()
    try:
        raw = client.fetch_values(
            is_dynasty=dynasty, num_qbs=num_qbs, num_teams=num_teams, ppr=ppr,
        )
    except Exception as exc:
        err_console.print(f"[red]Error fetching values:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output.write_text(json.dumps(raw, indent=2))
    console.print(f"[green]Exported {len(raw)} players to {output}[/green]")


if __name__ == "__main__":
    app()
