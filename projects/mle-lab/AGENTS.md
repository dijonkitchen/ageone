# mle-lab

A small ML system on real market data for learning ML engineering: S&P 500 volatility forecasts from FRED, DuckDB features, MLflow tracking, registry, and serving, and a daily feedback loop with an eval gate.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-10-16-mle-lab.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-16-mle-lab-stack.md): FRED, DuckDB, MLflow, and scikit-learn, and the MLflow quirks found on the way.
- [README](README.md): how to run it and things to try.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes. Tests need no network.
- `make fix`: apply lint and format fixes.
- `uv run mle fetch` then `uv run mle replay`: the loop on real data since 2019; needs network to FRED.

## Rules

- Never commit `data/`, `mlflow.db`, or `mlruns/`; FRED's S&P 500 data may not be redistributed.
- Pick registry models by alias (`champion`, `challenger`), never by stage or a hard-coded version.
- Anything that trains, evaluates, or monitors on a day uses only labels known by that day (`features.labeled`); a test checks the replay.
- Commit the lockfile (`uv.lock`) with any dependency change.
