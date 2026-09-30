# Decision Record 2026-09-30: Projects in ageone

## Status timeline

2026-09-30: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Bring JC's own projects into this monorepo, restarting each one here: fresh decision records, the same spec-first workflow, and the latest models, instead of carrying over each old repo's history and choices.

#### Non-functional

Keeps the [Structure](2026-09-25-structure.md) and [Conventions](2026-09-26-conventions.md): one `specs/PRIORITIES.md`, spec numbers unique across the repo, one `make` to set up.

### Nice to haves

#### Functional

Projects reuse this repo's shared parts: the model roles and eval runner from [SPEC-0002](../../specs/SPEC-0002-vendor-neutral-ai-harness.md), the pages from [SPEC-0004](../../specs/SPEC-0004-eval-benchmark-pages.md), and shared agent skills.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Porting old code line by line, or keeping old repos in sync with the new projects.

A build system spanning languages (Bazel, Nx, Pants): each project keeps its own plain toolchain.

#### Non-functional

## Decision

### Layout

Each project gets the same slug in three places:

- `projects/<slug>/`: the code, tests, and the project's own `README.md`.
- `specs/<slug>/`: its specs, numbered in the repo-wide `SPEC-NNNN` sequence and ranked in the one `specs/PRIORITIES.md`.
- `docs/decisions/<slug>/`: its decision records, in the usual format.

Shared agent skills live in `skills/<name>/`.
Decisions that apply to the whole repo stay directly in `docs/decisions/`.

### Starting anew

- The old repo is a reference only: read it for behavior, tests, and lessons, but don't copy its history or its decision records.
  Rebuild from the spec, test first.
- Each project's first decision record chooses its stack, citing the old repo's choice and whether it still holds.
- Old specs and acceptance criteria can be carried into the new spec, rewritten in this repo's format.
- A project's spec is `Done` when the rebuild meets its definition of done; JC then points the old repo's README here and archives it.

### Latest models

- Any LLM feature picks its model by role (such as `cheap` or `frontier`) through the model roles config from SPEC-0002, never a model ID in code, so moving to a newer model is a config change.
- The roles config tracks the newest models; when a new one ships, rerun the project's evals before switching its role.
- Work on the projects follows this repo's agent workflow, so current agents build them from the specs.

### Toolchains

Prefer the two ecosystems already in the old projects: TypeScript or plain JavaScript for browser apps, and Python with uv for data and back ends.
A project adds its toolchain to `devenv.nix`, so `make` still sets up everything, and CI runs a project's checks only when its folder changes.

Projects included, and why others aren't:

| Included | Old repo |
|---|---|
| connect6, og-trail, simplefit, fite, aiprofile, needle, roi, fread, sonal, posse-bliki, llm-from-scratch | JC's own code, with work to continue |
| `skills/prompt-injection-prevention` | JC's own skill, shared by projects that read untrusted text |

| Left out | Why |
|---|---|
| Forks (aleph, bidi, buddy-sign, compression, data.generators, doo, fela, idb, nvm, beebee, canvas-datagrid, calendar-maps, ForumMagnum, and others) | Other people's libraries; nothing of JC's to restart. Add a spec if a fork's idea becomes a project of its own. |
| ace | Empty repo with one initial commit. |
| Modin | JC's personal Obsidian vault: private notes, not a project. |
| statup, runconfig, dotfiles, dijonkitchen.github.io | Upptime config, dev-container dotfiles, and the personal site: infrastructure that works where it is. |
| agent-managers | A finished slide deck. |

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Restarting costs time, but each old project is small, and a rebuild from specs with current agents is quick and leaves every choice written down.

Several toolchains in one repo against [Structure](2026-09-25-structure.md)'s warning about multi-language monorepos: kept simple by giving each project its own folder and toolchain and no shared build system.

Old decision records aren't copied because their reasons may no longer hold; a new record can cite an old one.

### Dependencies

[SPEC-0005](../../specs/SPEC-0005-projects-scaffold.md) sets up the layout, toolchains, and per-project CI before any project starts.

### Interfaces

## Key Results and retrospective feedback
