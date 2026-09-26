# Decision Record 2026-09-26: Conventions

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

2026-09-26: Accepted by JC

2026-09-26: Amended by Claude, at JC's request: describe how the entry-point symlinks chain and behave.

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

- `README.md` holds the instructions for people and agents. It is the only one of the three that is a regular file.
- `AGENTS.md` (the cross-tool convention) is a symlink to `README.md`.
- `CLAUDE.md` (Claude Code) is a symlink to `AGENTS.md`, so it resolves to `README.md` through one hop.
  The chain is `CLAUDE.md` -> `AGENTS.md` -> `README.md`: the tool-specific name points at the cross-tool name, which points at the source.
- Edit `README.md` only. Editing either symlink in place writes through to `README.md`, but a tool that replaces the file instead of writing through turns the symlink into a copy and breaks the single source.
  If that happens, delete the copy and recreate the symlink with a relative target (`ln -s README.md AGENTS.md`, `ln -s AGENTS.md CLAUDE.md`).
- Git stores the symlinks themselves (mode `120000`), not the content, so the repo has one copy of the instructions.
  On a checkout that can't create symlinks, such as Windows without symlink support, each appears as a one-line file holding its target path; open the target by hand.
- Add a new entry-point name the same way: symlink it to `AGENTS.md`, never to `README.md` directly and never as a copy.

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
