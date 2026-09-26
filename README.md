# ageone

Monorepo for a super agentic project or monorepo of them.

`AGENTS.md` is a symlink to this file and `CLAUDE.md` is a symlink to `AGENTS.md`, so every agent, harness, and person reads the same instructions. Edit this file only.
Links are plain relative Markdown links: open each one you need to read.

## Read first

- [Structure](docs/decisions/2026-09-25-structure.md): where files live.
- [Conventions](docs/decisions/2026-09-26-conventions.md): naming, statuses, dates, and templates.
- [Priorities](specs/PRIORITIES.md): what to work on.

## Setup

Install [Nix and devenv](https://devenv.sh/getting-started/), then run `make setup`. Run `make` to list every target.

## Agent workflow

1. Read [`specs/PRIORITIES.md`](specs/PRIORITIES.md).
2. Take the highest priority spec (lowest number) whose status is `Open` and whose dependency is `Done` or `None`.
   Claim it by setting its status to `In progress (<owner>)`.
3. If nothing is open, or priorities look stale, reprioritize the table or write a new spec in `specs/`.
4. Whenever a spec is added or updated, re-evaluate the whole priority table, then update `updated_at` in `specs/PRIORITIES.md`.
5. Keep the spec's status in `specs/PRIORITIES.md` current as you go; set it to `Done` when its definition of done is met.
6. Record any decisions as decision records (ADRs), especially architectural decisions, in `docs/decisions/`.
