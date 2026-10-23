# fite

"Shell Shock", a browser tournament fighter with four turtle ninjas and a boss, drawn as procedural pixel art with synthesized sound, for anyone with a keyboard, a gamepad, or a phone.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-fite-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-fite-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run build`: build the game into `dist/` (the Site workflow publishes it at `fite/` on Pages); serve `dist/` with any static server to play.
- `bun run harness 50 hard easy`: headless CPU-versus-CPU matches and win rates.
- `bun run sheet`: redraw `sprites/sheet.png` after changing the sprite code.

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- No asset files: art, text, and sound are generated in code. `sprites/sheet.png` is generated too, and a test checks it matches.
- Keep `src/sim.ts` pure and deterministic: no randomness, clock, or DOM. The CPU plays only through input bitmasks.
- CPU levels may change reaction and choices, never damage or speed.
- No copyrighted characters, names, or assets.
