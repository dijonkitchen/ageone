# og-trail

The Oregon Trail for modern life (rent, student loans, burnout, 2,000 miles to Stability), with random, rule-based, and LLM players so it doubles as a long-horizon eval.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-og-trail-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-04-og-trail-stack.md): Python 3.11+, uv, ruff, mypy, pytest, and the standard library only.
- [README](README.md): how to play and how to run agent players.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `uv run og-trail batch --player rules`: 20 seeded games per profession, one NDJSON line each.

## Rules

- Commit `uv.lock` with any dependency change; the engine and players take none at runtime.
- Every frontend and player goes through `Game.view()` and `Game.submit()`; rules live in `engine.py`, data in `content.py`, `events.py`, and `landmarks.py`.
- Adding an event or landmark is data only; the tests pick up every entry in `EVENTS` and `LANDMARKS`.
- The LLM player picks its model by role from the root `harness/models.json`; never put a model ID in code.
