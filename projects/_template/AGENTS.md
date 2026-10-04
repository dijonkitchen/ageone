# __PROJECT__

One or two sentences on what __PROJECT__ is and who it is for.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/): what to build and the definition of done.
- [Stack decision](docs/decisions/__DATE__-__PROJECT__-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
