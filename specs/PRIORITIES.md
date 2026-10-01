# Priorities

updated_at: 2026-10-01

Table of specs, listing their number, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Rows are sorted by priority (highest first), then by difficulty (easiest first).
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

| Number | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-0003](SPEC-0003-make-setup.md) | None | 1 | Make setup: one idempotent `make` installs Nix and devenv, builds the pinned environment (Node.js LTS for pi), and checks it | Low | Done |
| [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) | SPEC-0001 | 2 | Vendor-neutral AI harness: pi + model roles config + web search + private open-weight models + evals on our own tasks, with a runner that swaps harnesses or calls models directly | Medium | Blocked (needs an OPENROUTER_API_KEY to run definition of done items 1-3, 5, and 6) |
| [SPEC-0004](SPEC-0004-eval-benchmark-pages.md) | SPEC-0002 | 3 | Eval and benchmark pages: static site of our experiments comparing ways to do things (output formats like TOON vs CSV vs JSON, tool interfaces, harnesses) across models | Medium | Blocked (needs an OPENROUTER_API_KEY for definition of done items 2, 3, and 5, and GitHub Pages enabled for publishing) |
| [SPEC-0005](SPEC-0005-tile-laying-game.md) | SPEC-0003 | 4 | Tile-laying game: two-player, one-device Carcassonne-style browser game on tournament rules, with a generated tile set each game and a JSON game file that saves and loads any state | Medium | Open |
| [SPEC-0006](SPEC-0006-algorithm-roguelike.md) | SPEC-0003 | 5 | Algorithm roguelike: a browser roguelike where learning an algorithm or data structure (by puzzle or by writing code) unlocks it as a game system, so the dungeon grows with the player | High | Open |
| [SPEC-0001](SPEC-0001-agent-todo-repo.md) | None | 6 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
