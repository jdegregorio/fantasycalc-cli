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

## What’s new in this CLI

The CLI now emphasizes discoverability and day-to-day usability:

- Strong validation for league/scoring settings, including `--ppr 0.5`
- Clear command feedback telling you whether data came from the API or cache
- Built-in cache controls with `--cache-ttl`, `--no-cache`, and `--refresh-cache`
- Rich filtering and sorting for `values`
- JSON and CSV export from both `values` and `export`
- Exact-match search with `lookup --exact`
- Cache maintenance via `fantasycalc cache clear`

## Usage

### Discover features quickly

```bash
fantasycalc --help
fantasycalc values --help
fantasycalc lookup --help
fantasycalc export --help
fantasycalc index --help
fantasycalc cache clear --help
```

### Fetch current dynasty values

```bash
# Top 50 superflex dynasty values (default)
fantasycalc values

# Redraft, 1QB, half-PPR
fantasycalc values --redraft --num-qbs 1 --ppr 0.5

# Filter by position and team, sort by value descending
fantasycalc values --position QB --team BUF --sort value --desc

# Show risers in CSV format
fantasycalc values --sort trend30Day --desc --format csv

# Filter by age/value and write JSON to a file
fantasycalc values --age-max 25 --min-value 5000 --format json --output young-stars.json
```

### Look up a player

```bash
fantasycalc lookup --name "Patrick Mahomes"
fantasycalc lookup --name chase --format json
fantasycalc lookup --name "Josh Allen" --exact --format csv
```

### Export full values to a file

```bash
fantasycalc export --output values.json
fantasycalc export --output values.csv --format csv
fantasycalc export --output redraft.json --redraft --num-qbs 1 --ppr 0.5
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
    "sleeperId": "4984"
  }
}
```

### Cache controls

```bash
# Prefer cached data for 10 minutes
fantasycalc values --cache-ttl 600

# Force a fresh API request and refresh local cache
fantasycalc values --refresh-cache

# Disable cache entirely
fantasycalc values --no-cache

# Clear all cached responses
fantasycalc cache clear
```

### JSON/CSV output schema

When using `--format json` or `--format csv`, each player row includes:

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

### Core options available on fetch commands

| Flag | Default | Description |
|------|---------|-------------|
| `--dynasty / --redraft` | dynasty | Dynasty or redraft values |
| `--num-qbs` | 2 | Starting QBs (`1` or `2`) |
| `--num-teams` | 12 | League size (`2` to `32`) |
| `--ppr` | 1 | Points per reception (`0`, `0.5`, or `1`) |
| `--cache-ttl` | 300 | Reuse cached values newer than this many seconds |
| `--use-cache / --no-cache` | use-cache | Enable or disable cache reads/writes |
| `--refresh-cache` | off | Bypass cache reads and refresh from the API |

## Development

```bash
# Lint
uv run ruff check src/ tests/

# Test
uv run pytest -v
```

## License

MIT
