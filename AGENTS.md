# Helix Agent Notes

## Build Commands

- `pip install -e ".[dev]"`
- `helix --help`
- `helix --version`

## Test Commands

- `pytest tests/ -x -q`
- `pytest tests/ -x -q --cov=helix --cov-report=term-missing`
- `ruff check helix/`
- `mypy helix/ --ignore-missing-imports`

## Package Conventions

- Project name: Helix
- Package name: `helix`
- CLI command: `helix`
- Python 3.11+
- Public modules use `from __future__ import annotations`

## Naming

- Do not use AgentOpt naming in code, config, CLI, SQL, YAML, README, or tests.
- Use `HELIX_CACHE_PATH`, `HELIX_GRAPH_PATH`, and `HELIX_LLM_BACKEND`.

## v0 Constraints

- The fake backend must work without API keys and must remain deterministic.
- SQLite only for v0 cache and graph persistence.
- Use Rich for CLI output.

