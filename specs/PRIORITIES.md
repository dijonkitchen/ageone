# Priorities

updated_at: 2026-10-03

Table of specs, listing their number, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Rows are sorted by priority (highest first), then by difficulty (easiest first).
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

| Number | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-0003](SPEC-0003-make-setup.md) | None | 1 | Make setup: one idempotent `make` installs Nix and devenv, builds the pinned environment (Node.js LTS for pi), and checks it | Low | Done |
| [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) | SPEC-0001 | 2 | Vendor-neutral AI harness: pi + model roles config + web search + private open-weight models + evals on our own tasks, with a runner that swaps harnesses or calls models directly | Medium | Open |
| [SPEC-0004](SPEC-0004-eval-benchmark-pages.md) | SPEC-0002 | 3 | Eval and benchmark pages: static site of our experiments comparing ways to do things (output formats like TOON vs CSV vs JSON, tool interfaces, harnesses) across models | Medium | Open |
| [SPEC-0007](stock-screener/SPEC-0007-stock-screener.md) | SPEC-0003 | 4 | Stock screener: pulls the latest SEC EDGAR XBRL filings into 10+ years of split-adjusted per-share history (BVPS, EPS, FCF, dividends) and ratios, then filters, sorts, and ranks companies interactively by growth, consistency, and a composite score | Medium | Open |
| [SPEC-0008](stock-screener/SPEC-0008-portfolio-kelly.md) | SPEC-0007 | 5 | Portfolio and Kelly allocation: live prices and price ratios (now and over 10+ years), an interactive portfolio built from screen results, and fractional Kelly position sizing with constraints and a sensitivity view | High | Open |
| [SPEC-0005](SPEC-0005-tile-laying-game.md) | SPEC-0003 | 6 | Tile-laying game: two-player, one-device Carcassonne-style browser game on tournament rules, with a generated tile set each game and a JSON game file that saves and loads any state | Medium | Open |
| [SPEC-0009](SPEC-0009-anatomy-viewer.md) | SPEC-0003 | 7 | Anatomy viewer: interactive SVG views of the human body (front, back, side) with toggleable system layers, pickable structures with details and relations, and search, with the skeleton rigged at joints so movement can follow in a later spec | Medium | Open |
| [SPEC-0006](SPEC-0006-algorithm-roguelike.md) | SPEC-0003 | 8 | Algorithm roguelike: a browser roguelike where learning an algorithm or data structure (by puzzle or by writing code) unlocks it as a game system, so the dungeon grows with the player | High | Open |
| [SPEC-0001](SPEC-0001-agent-todo-repo.md) | None | 9 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
