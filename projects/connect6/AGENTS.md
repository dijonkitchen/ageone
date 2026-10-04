# connect6

Connect6 (19×19, Black opens with one stone, then two per turn, six in a row wins) with a pure engine, random, heuristic, MCTS, and LLM players, a web UI, and a headless tournament that doubles as an agent benchmark.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-connect6-rebuild.md): what to build and the definition of done.
- [Rules](specs/rules.md): the game's acceptance criteria; every test name cites one.
- [Stack decision](docs/decisions/2026-10-04-connect6-stack.md): TypeScript on Bun, Biome, and Bun's own bundler and server.
- [README](README.md): how to play and run tournaments.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `bun run dev`: the web UI at http://localhost:3000.
- `bun run tournament --players mcts,heuristic --games 100`: NDJSON results on stdout.

## Rules

- Commit `bun.lock` with any dependency change; there are no runtime dependencies.
- `src/core` stays pure: no DOM, network, filesystem, or clock. Model calls reach the LLM player as an injected `Chat` function.
- A new rule or player behaviour gets an acceptance criterion in `specs/rules.md` and a test citing it; the traceability test fails otherwise.
- The LLM player picks its model by role from the root `harness/models.json`; never put a model ID in code.
