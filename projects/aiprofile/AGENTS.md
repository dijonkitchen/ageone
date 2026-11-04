# aiprofile

An AI-maintained work profile: a worker signs in with GitHub, and an LLM proposes profile changes that each cite verified evidence, which the worker accepts or rejects.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-aiprofile-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `make run`: migrate, then run the worker and the app at `localhost:8000` (needs `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `OPENROUTER_API_KEY`).

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- No claim reaches a profile without cited evidence and the worker's acceptance; keep `synth.parse_claims` the only way a model answer becomes a claim.
- Model IDs come from `harness/models.json` roles, never code.
