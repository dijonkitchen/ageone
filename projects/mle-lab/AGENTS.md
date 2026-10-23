# mle-lab

A small ML system on real grid data for learning ML engineering: day-ahead hourly demand forecasts for ERCOT from EIA-930, DuckDB features, MLflow tracking, registry, and serving, and a daily feedback loop with an eval gate.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-10-16-mle-lab.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-16-mle-lab-stack.md): EIA-930, DuckDB, MLflow, and scikit-learn, and the MLflow quirks found on the way.
- [README](README.md): how to run it, results, and things to try.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes. Tests need no network: they use real ERCOT hours committed in `tests/data/`.
- `make fix`: apply lint and format fixes.
- `uv run mle fetch` then `uv run mle replay`: the loop on real data since 2024; needs network to eia.gov.

## Rules

- Never commit `data/`, `mlflow.db`, or `mlruns/`; they are large and rebuilt by `mle`. EIA data is public domain, so small fixtures may be committed under `tests/data/`.
- Pick registry models by alias (`champion`, `challenger`), never by stage or a hard-coded version.
- A forecast for day D uses only demand through the end of D-2, and anything that trains, evaluates, or monitors on a morning uses only labels known by then (`features.labeled`); tests check both.
- Commit the lockfile (`uv.lock`) with any dependency change.
