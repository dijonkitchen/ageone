# needle

A local-first research assistant that runs in the browser: ask a question, it searches the web, writes a cited answer, and saves it as an Obsidian-ready Markdown note, for people who want their research in files they own.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-needle-walking-skeleton.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-needle-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and unit tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `make e2e`: build the PWA and run the end-to-end tests in Chromium (needs one installed, such as `bunx playwright-core install chromium`).
- `bun run build`: build the PWA into `dist/`; serve it with any static server to try it.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Never put search results or model text into the page as HTML; use `textContent`.
- Anything fetched from the web reaches a model only through `sourcesBlock()` in `src/untrusted.ts`.
- No model ID in code: pick a role from `harness/models.json`.
- Each milestone outcome gets an end-to-end test in `e2e/` before its code.
