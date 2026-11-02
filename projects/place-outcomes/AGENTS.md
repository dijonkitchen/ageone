# place-outcomes

Schools, homes, and outcomes by place: joins area-level factors to adult outcomes (Opportunity Atlas) and home values (Zillow) by ZIP code in California and New Jersey, for people choosing where to live and for learning data science and ML engineering.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-11-02-place-outcomes-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
