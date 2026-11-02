# place-outcomes

Schools, homes, and outcomes by place: public area-level data for California and New Jersey, joined by ZIP, with a monthly home value forecast that retrains behind an eval gate.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-11-02-place-outcomes.md): what to build and the definition of done.
- [Data and stack decision](docs/decisions/2026-11-02-place-outcomes-data.md): the sources, the toolchain, and why.
- [README](README.md): how to run it and what the last full replay showed.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `uv run places --help`: the CLI.

## Rules

- Commit the lockfile (`uv.lock`) with any dependency change.
- Nothing personal is committed: no shortlist, budget, or home search. Places to highlight go in the git-ignored `places.local.toml`.
- Race and ethnicity composition is a control or a described covariate, never a score that ranks places.
- Credit Zillow ("Data provided by Zillow") wherever its numbers appear.
