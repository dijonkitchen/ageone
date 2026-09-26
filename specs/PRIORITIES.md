# Priorities

updated_at: 2026-09-26

Table of specs, listing their number, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

| Number | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-0001](SPEC-0001-agent-todo-repo.md) | None | 2 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
| [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) | SPEC-0001 | 1 | Vendor-neutral AI harness: pi + model roles config + evals on our own tasks | Medium | Open |
