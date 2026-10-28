# fread

A private RSS and Atom reader that runs entirely in the browser and installs as a PWA, for people who want feeds without accounts, servers, or tracking.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-fread-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-fread-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the PWA into `dist/` (the Site workflow publishes it at `fread/` on Pages); serve `dist/` with any static server to try it.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Never put feed text into the page as HTML except through `sanitize()`; use `textContent` everywhere else.
- No request may leave the page except to a feed, the user's proxy, or (with summaries on) the model endpoint: no analytics, fonts, or CDNs.
- Feed samples in `test/fixtures/` are recorded real feeds; add one for any format bug before fixing it.
