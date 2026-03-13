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
