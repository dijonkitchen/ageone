# Decision Record 2026-09-26: Conventions

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

2026-09-26: Accepted by JC

2026-09-26: Amended by Claude, at JC's request: describe how the entry-point symlinks chain and behave.

2026-09-26: Amended by Claude, at JC's request: sort the priority table by priority, then difficulty.

2026-09-27: Amended by Claude, at JC's request: pull request descriptions stay light; commit messages hold the detail.

2026-09-27: Amended by Claude, at JC's request: pull request titles use the Conventional Commits format, because pull requests are squash merged.

2026-09-27: Amended by Claude, at JC's request: a CI check enforces pull request titles; list the allowed types.

2026-09-28: Amended by Claude, at JC's request: Markdown prose uses semantic line breaks.

2026-10-03: Amended by Claude, at JC's request: specs are named by date and slug instead of a sequential number, so parallel work can't collide on the next number.

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
Pull request titles needed it first, since squash merges carry them onto `main`.

#### Non-functional

## Decision

### General

- Files are Markdown, one `#` title per file.
- File names are kebab-case.
- Dates are ISO 8601 (`YYYY-MM-DD`), UTC.
- Prose uses [semantic line breaks](https://sembr.org): one sentence per line, so diffs and reviews show the sentence that changed.
  Markdown joins consecutive lines into one paragraph, so the rendered output is unchanged; a blank line starts a new paragraph.
- Links between files are relative Markdown links, such as `[Priorities](specs/PRIORITIES.md)`, which every agent, harness, and Git host can follow.

### Agent entry points

- `README.md` holds the instructions for people and agents.
  It is the only one of the three that is a regular file.
- `AGENTS.md` (the cross-tool convention) is a symlink to `README.md`.
- `CLAUDE.md` (Claude Code) is a symlink to `AGENTS.md`, so it resolves to `README.md` through one hop.
  The chain is `CLAUDE.md` -> `AGENTS.md` -> `README.md`: the tool-specific name points at the cross-tool name, which points at the source.
- Edit `README.md` only.
  Editing either symlink in place writes through to `README.md`, but a tool that replaces the file instead of writing through turns the symlink into a copy and breaks the single source.
  If that happens, delete the copy and recreate the symlink with a relative target (`ln -s README.md AGENTS.md`, `ln -s AGENTS.md CLAUDE.md`).
- Git stores the symlinks themselves (mode `120000`), not the content, so the repo has one copy of the instructions.
  On a checkout that can't create symlinks, such as Windows without symlink support, each appears as a one-line file holding its target path; open the target by hand.
- Add a new entry-point name the same way: symlink it to `AGENTS.md`, never to `README.md` directly and never as a copy.

### Specs

- Path: `specs/SPEC-YYYY-MM-DD-short-slug.md`, or `specs/<project>/SPEC-YYYY-MM-DD-short-slug.md` once a project needs its own folder.
- The file name without `.md` is the spec's ID, such as `SPEC-2026-10-03-stock-screener`.
  The date is when the spec is proposed, so IDs sort in the order specs were written.
- IDs are unique across the whole repo and never reused, but nobody hands them out: parallel work picks its own date and slug.
  If an ID is already taken, append `-2` (then `-3`, and so on) to the slug.
- Title: `# SPEC-YYYY-MM-DD-short-slug: Title`.
- Sections: `## Functional requirements`, `## Non-functional requirements`, `## Definition of done`.
  A spec can't be `Done` without a definition of done.

### Priorities

- `specs/PRIORITIES.md` has one row per spec.
- Rows are sorted by priority (highest first), then by difficulty (`Low` before `Medium` before `High`), so the top open row is the next one to take.
- `updated_at` at the top is the date of the last change to the table.
- Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.
- Priority: integer, `1` is the highest.
- Dependency: a spec ID, or `None`.
- Difficulty: `Low`, `Medium`, or `High`.
- Status: `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.
  The owner is a person's handle or an agent session, and claims the spec so others pick a different one.

### Decision records

- Path: `docs/decisions/YYYY-MM-DD-short-slug.md`, dated when proposed.
- Covers any decision (ADRs), especially architectural decisions.
- Title: `# Decision Record YYYY-MM-DD: Title`.
- Follow the sections of [decision records](2026-09-25-decision-records.md).
  Sections can be left empty.
- Status timeline entries: `YYYY-MM-DD: <Proposed|Accepted|Amended|Rejected|Superseded by <record>> by <name>`.
- Don't rewrite an accepted decision's substance.
  Add an `Amended` entry for small clarifications, or write a new record that supersedes it.

### Commits and pull requests

Conventional Commits: `type(optional-scope): summary`, with `!` before the colon for a breaking change.
Types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`.

Pull requests are squash merged, so the pull request title becomes the commit subject on `main`.
Pull request titles follow the same format as commits, such as `docs: add a spec for eval and benchmark pages`, and are updated if the change's scope shifts before merge.
The [PR title workflow](../../.github/workflows/pr-title.yml) fails a pull request whose title doesn't match; it is the source of truth for the pattern.

Commit messages hold the detail for the long term: what changed and why.
Pull request descriptions stay light: a few lines on the goal and how to verify it, pointing to the commits, specs, and decision records instead of repeating them.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Relative Markdown links over `@` imports: `@` imports only work in Claude Code and show as literal text elsewhere, including on GitHub.

Owner inside the status column instead of a separate column: keeps the table small; add a column if parallel work grows.

### Dependencies

### Interfaces

## Key Results and retrospective feedback
