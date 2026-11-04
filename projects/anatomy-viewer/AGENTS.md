# anatomy-viewer

An interactive SVG view of the human body for learners: turn body systems on and off, pick a structure to see what it is and what it connects to, and search by common or Latin name.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-10-03-anatomy-viewer.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-anatomy-viewer-stack.md): the toolchain, the data file, the FMA ids, and the sources and licenses.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the static page into `dist/`.
- `bun run serve`: build and serve it at `http://localhost:8080/` (`PORT` changes the port).
- `bun run verify`: check the data file against FMA and Wikipedia over the network; run it after changing names or relations.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Names, relations, and descriptions live only in `data/anatomy.json`, keyed by FMA ids; drawings in `src/drawings.ts` refer to structures by their data name.
- A structure in the data is drawn in some view or carries a `notDrawn` reason; the tests enforce it.
- Write descriptions in your own words: sources are for checking facts, not for copying text.
