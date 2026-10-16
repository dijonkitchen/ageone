# mle-lab

A small, complete ML system to learn ML engineering on: DuckDB features, MLflow tracking, registry, and serving, monitoring, and a feedback loop that retrains on new labels behind evals.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-10-16-mle-lab.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-16-mle-lab-stack.md): Python with uv, DuckDB, MLflow, and scikit-learn, and the MLflow quirks found on the way.
- [README](README.md): how to run it and what each stage teaches.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `uv run mle all`: the whole system and loop on generated data, writing `data/`, `mlflow.db`, and `mlruns/` here.

## Rules

- Commit the lockfile (`uv.lock`) with any dependency change.
- Never commit `data/`, `mlflow.db`, or `mlruns/`.
- Pick registry models by alias (`champion`, `challenger`), never by stage or a hard-coded version.
- Training must never see the month it is evaluated on; `train.train` refuses, and a test checks the loop.
