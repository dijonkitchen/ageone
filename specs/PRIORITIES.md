# Priorities

updated_at: 2026-10-03

Table of specs, listing their ID, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Rows are sorted by priority (highest first), then by difficulty (easiest first).
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

| Spec | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-2026-09-26-make-setup](SPEC-2026-09-26-make-setup.md) | None | 1 | Make setup: one idempotent `make` installs Nix and devenv, builds the pinned environment (Node.js LTS for pi), and checks it | Low | Done |
| [SPEC-2026-09-26-vendor-neutral-ai-harness](SPEC-2026-09-26-vendor-neutral-ai-harness.md) | SPEC-2026-09-25-agent-todo-repo | 2 | Vendor-neutral AI harness: pi + model roles config + web search + private open-weight models + evals on our own tasks, with a runner that swaps harnesses or calls models directly | Medium | Open |
| [SPEC-2026-09-27-eval-benchmark-pages](SPEC-2026-09-27-eval-benchmark-pages.md) | SPEC-2026-09-26-vendor-neutral-ai-harness | 3 | Eval and benchmark pages: static site of our experiments comparing ways to do things (output formats like TOON vs CSV vs JSON, tool interfaces, harnesses) across models | Medium | Open |
| [SPEC-2026-10-03-stock-screener](stock-screener/SPEC-2026-10-03-stock-screener.md) | SPEC-2026-09-26-make-setup | 4 | Stock screener: pulls the latest SEC EDGAR XBRL filings into 10+ years of split-adjusted per-share history (BVPS, EPS, FCF, dividends) and ratios, then filters, sorts, and ranks companies interactively by growth, consistency, and a composite score | Medium | In progress (Claude) |
| [SPEC-2026-10-03-portfolio-kelly](stock-screener/SPEC-2026-10-03-portfolio-kelly.md) | SPEC-2026-10-03-stock-screener | 5 | Portfolio and Kelly allocation: live prices and price ratios (now and over 10+ years), an interactive portfolio built from screen results, and fractional Kelly position sizing with constraints and a sensitivity view | High | Open |
| [SPEC-2026-09-30-tile-laying-game](SPEC-2026-09-30-tile-laying-game.md) | SPEC-2026-09-26-make-setup | 6 | Tile-laying game: two-player, one-device Carcassonne-style browser game on tournament rules, with a generated tile set each game and a JSON game file that saves and loads any state | Medium | Open |
| [SPEC-2026-10-03-anatomy-viewer](SPEC-2026-10-03-anatomy-viewer.md) | SPEC-2026-09-26-make-setup | 7 | Anatomy viewer: interactive SVG views of the human body (front, back, side) with toggleable system layers, pickable structures with details and relations, and search, with the skeleton rigged at joints so movement can follow in a later spec | Medium | Open |
| [SPEC-2026-09-30-algorithm-roguelike](SPEC-2026-09-30-algorithm-roguelike.md) | SPEC-2026-09-26-make-setup | 8 | Algorithm roguelike: a browser roguelike where learning an algorithm or data structure (by puzzle or by writing code) unlocks it as a game system, so the dungeon grows with the player | High | Open |
| [SPEC-2026-09-25-agent-todo-repo](SPEC-2026-09-25-agent-todo-repo.md) | None | 9 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
