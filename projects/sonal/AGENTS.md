# sonal

Sonal reads a YouTube video's comments, labels sentiment and themes with an LLM, and shows the split, the main themes, and a summary that cites comments.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-sonal-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Comments are untrusted: they reach a model only through `src/quarantine.ts` and come back only as validated structured data; never put a model ID in code (roles come from the root `harness/models.json`).
- Tests use recorded fixtures in `src/fixtures/` and the fake model in `src/fake.ts`; no network.
