# tile-laying-game

"Tile Towns", a two-player, one-device tile-laying game in the browser on the base game's tournament rules, with a freshly generated, balanced tile set each game and a JSON game file that saves and loads any position.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-tile-laying-game.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-tile-laying-game-stack.md): the toolchain, the tile code, and the game file format.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the static page into `dist/`.
- `bun run serve`: build and play it at <http://localhost:8080/> (`PORT` picks another port).

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- Every game state change goes through `src/engine.ts`; keep it pure and deterministic (no randomness, clock, or DOM).
- Tiles are drawn from the same geometry that decides their features (`src/tiles.ts`); never draw a tile some other way.
- Bump `FORMAT` in `src/file.ts` if the game file's shape changes.
- No publisher names, logos, art, or rulebook text.
