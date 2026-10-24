# algorithm-roguelike

A browser roguelike where learning an algorithm or data structure, by puzzle or by writing it, unlocks it as part of the game, so the dungeon grows with the player.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-algorithm-roguelike.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-algorithm-roguelike-stack.md): TypeScript, ASCII rendering, determinism, and the QuickJS code-mode sandbox.
- [Adding a concept](docs/adding-a-concept.md): a folder and one line, never an engine change.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, tests, and the build; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the page into `dist/`.
- `bun run serve`: build and serve it at `http://localhost:8080/` (`PORT` changes the port).

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- `src/core/` must not name or import a concept; concepts reach the game only through hooks.
- All randomness inside a run goes through the run's `Rng` (`ctx.rng`), never `Math.random`, so runs replay.
- Puzzle answers come from the reference implementation, never typed by hand.
