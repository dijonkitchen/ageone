# Priorities

updated_at: 2026-09-27

Table of specs, listing their number, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Rows are sorted by priority (highest first), then by difficulty (easiest first).
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

| Number | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-0003](SPEC-0003-make-setup.md) | None | 1 | Make setup: one idempotent `make` installs Nix and devenv, builds the pinned environment (Node.js LTS for pi), and checks it | Low | Done |
| [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) | SPEC-0001 | 2 | Vendor-neutral AI harness: pi + model roles config + web search + private open-weight models + evals on our own tasks | Medium | Open |
| [SPEC-0001](SPEC-0001-agent-todo-repo.md) | None | 3 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
