# stock-screener

Screens US-listed companies on 10+ years of split-adjusted per-share history from SEC EDGAR XBRL filings.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-10-03-stock-screener.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-03-stock-screener-stack.md): Python with uv, OpenBB's SEC provider, DuckDB, pandas, and Streamlit.
- [README](README.md): commands and how the pipeline fits together.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint and tests, as CI runs them whenever this folder changes.
- `uv run pytest`: tests on recorded fixtures, no network.
- `uv run ruff check .`: lint.
- `uv run screener refresh --tickers AAPL,MSFT` then `uv run screener spot-check`: compare loaded values with the 10-K numbers in `spot_check.toml`; needs SEC access and a `config.toml` (git-ignored) copied from `config.example.toml`.

## Rules

- Never commit `config.toml` or `screener.duckdb`.
- The SEC rejects some User-Agent strings (anything with a github.com address); use a `Name contact@domain` form.
- After an OpenBB upgrade, rerun the spot check, then regenerate fixtures with `uv run python tests/record_standardized.py`.
