# fantasycalc-cli

A command-line interface for the [FantasyCalc](https://fantasycalc.com) dynasty fantasy football valuation API.

## Installation

```bash
pip install .
```

For development:

```bash
uv sync
```

## Usage

### Fetch current dynasty values

```bash
# Top 50 superflex dynasty values (default)
fantasycalc values

# Redraft, 1QB, PPR
fantasycalc values --redraft --num-qbs 1

# Filter by position, output as JSON
fantasycalc values --position QB --format json --limit 10
```

### Look up a player

```bash
fantasycalc lookup --name "Patrick Mahomes"
fantasycalc lookup --name chase --format json
```

### Export full values to a file

```bash
fantasycalc export --output values.json
fantasycalc export --output redraft.json --redraft --num-qbs 1
```

### Index values by platform ID

Build a platform-ID-keyed JSON mapping for cross-platform joins:

```bash
# Index by Fleaflicker ID (stdout)
fantasycalc index --platform fleaflicker

# Index by Sleeper ID and write to file
fantasycalc index --platform sleeper --output sleeper-index.json
```

Supported platforms: `espn`, `fleaflicker`, `mfl`, `sleeper`, `yahoo`.

Output shape:

```json
{
  "13761": {
    "name": "Josh Allen",
    "position": "QB",
    "team": "BUF",
    "value": 10358,
    "fleaflickerId": "13761",
    "sleeperId": "4984",
    ...
  }
}
```

### JSON output schema

When using `--format json`, each player row includes:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Player name |
| `position` | string | Position (QB, RB, WR, TE) |
| `team` | string | NFL team abbreviation |
| `age` | int | Player age |
| `value` | int | FantasyCalc market value |
| `overallRank` | int | Overall dynasty rank |
| `positionRank` | int | Position dynasty rank |
| `playerId` | int/null | FantasyCalc internal player ID |
| `fleaflickerId` | string/null | Fleaflicker platform ID |
| `sleeperId` | string/null | Sleeper platform ID |
| `espnId` | string/null | ESPN platform ID |
| `mflId` | string/null | MFL platform ID |
| `yahooId` | string/null | Yahoo platform ID |
| `trend30Day` | number/null | 30-day value trend |
| `displayTrend` | string/null | Trend display label |

### Options available on all fetch commands

| Flag | Default | Description |
|------|---------|-------------|
| `--dynasty / --redraft` | dynasty | Dynasty or redraft values |
| `--num-qbs` | 2 | Starting QBs (2 = superflex) |
| `--num-teams` | 12 | League size |
| `--ppr` | 1 | Points per reception |

## Development

```bash
# Lint
uv run ruff check src/ tests/

# Test
uv run pytest -v
```

## License

MIT
