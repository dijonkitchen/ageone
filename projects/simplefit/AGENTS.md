# simplefit

A small, private, offline-first fitness PWA for health and longevity that tracks only the best-evidenced metrics (Zone 2 and Zone 4 minutes, strength sessions, resting heart rate, VO₂max) and says what to do next.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-simplefit-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-simplefit-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the PWA into `dist/` (the Site workflow publishes it at `simplefit/` on Pages); serve `dist/` with any static server to try it.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Every formula cites its source in the code and is tested against that source's numbers; check a citation (for example its DOI on Crossref) before adding it.
- Data never leaves the device except in an export the user starts: no requests beyond the app's own files.
- Bump nothing by hand for releases: the build fingerprints the files, and the service worker caches each version whole.
- Backup files keep `version: 1` readable; add fields with defaults rather than changing old ones.
