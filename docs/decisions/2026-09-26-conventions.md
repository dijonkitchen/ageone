# Decision Record 2026-09-26: Conventions

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Written conventions, taken from the files already in the repo, so people and agents name, order, and update specs and decision records the same way.

#### Non-functional

Works with any agent or harness, not only one tool.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Tooling or linting to enforce conventions before they're needed.

#### Non-functional

## Decision

### General

- Files are Markdown, one `#` title per file.
- File names are kebab-case.
- Dates are ISO 8601 (`YYYY-MM-DD`), UTC.
- Links between files are relative Markdown links, such as `[Priorities](specs/PRIORITIES.md)`, which every agent, harness, and Git host can follow.

### Agent entry points

- `README.md` holds the instructions for people and agents.
- `AGENTS.md` (the cross-tool convention) and `CLAUDE.md` (Claude Code) are symlinks to `README.md`, so there's one source.

### Specs

- Path: `specs/SPEC-NNNN-short-slug.md`, or `specs/<project>/SPEC-NNNN-short-slug.md` once a project needs its own folder.
- `NNNN` is a zero-padded number, unique across the whole repo, given in order and never reused.
- Title: `# SPEC-NNNN: Title`.
- Sections: `## Functional requirements`, `## Non-functional requirements`, `## Definition of done`.
  A spec can't be `Done` without a definition of done.

### Priorities

- `specs/PRIORITIES.md` has one row per spec.
- `updated_at` at the top is the date of the last change to the table.
- Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.
- Priority: integer, `1` is the highest.
- Dependency: a spec number, or `None`.
- Difficulty: `Low`, `Medium`, or `High`.
- Status: `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.
  The owner is a person's handle or an agent session, and claims the spec so others pick a different one.

### Decision records

- Path: `docs/decisions/YYYY-MM-DD-short-slug.md`, dated when proposed.
- Covers any decision (ADRs), especially architectural decisions.
- Title: `# Decision Record YYYY-MM-DD: Title`.
- Follow the sections of [decision records](2026-09-25-decision-records.md). Sections can be left empty.
- Status timeline entries: `YYYY-MM-DD: <Proposed|Accepted|Amended|Rejected|Superseded by <record>> by <name>`.
- Don't rewrite an accepted decision's substance. Add an `Amended` entry for small clarifications, or write a new record that supersedes it.

### Commits

Conventional Commits prefixes, as already used: `docs:`, `build:`, `feat:`, `fix:`, `chore:`.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Relative Markdown links over `@` imports: `@` imports only work in Claude Code and show as literal text elsewhere, including on GitHub.

Owner inside the status column instead of a separate column: keeps the table small; add a column if parallel work grows.

### Dependencies

### Interfaces

## Key Results and retrospective feedback
