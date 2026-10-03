# Decision Record 2026-09-30: Projects in ageone

## Status timeline

2026-09-30: Proposed by Claude, at JC's request

2026-09-30: Amended by Claude, at JC's request, before acceptance: each project's specs, decision records, and a nested `AGENTS.md` live in its project folder.

2026-10-03: Amended by Claude, at JC's request, before acceptance: a project gets its nested `AGENTS.md` from the template once it has code, not as a stub; specs are named by date; the stock screener, tile-laying game, algorithm roguelike, and anatomy viewer specs move into project folders too.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Bring JC's own projects into this monorepo, restarting each one here: fresh decision records, the same spec-first workflow, and the latest models, instead of carrying over each old repo's history and choices.

#### Non-functional

Keeps the [Structure](2026-09-25-structure.md) and [Conventions](2026-09-26-conventions.md): one `specs/PRIORITIES.md`, spec numbers unique across the repo, one `make` to set up.

### Nice to haves

#### Functional

Projects reuse this repo's shared parts: the model roles and eval runner from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md), the pages from [SPEC-2026-09-27-eval-benchmark-pages](../../specs/SPEC-2026-09-27-eval-benchmark-pages.md), and shared agent skills.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Porting old code line by line, or keeping old repos in sync with the new projects.

A build system spanning languages (Bazel, Nx, Pants): each project keeps its own plain toolchain.

#### Non-functional

## Decision

### Layout

Each project is self-contained in `projects/<slug>/`:

- `AGENTS.md`, with `CLAUDE.md` symlinked to it, added from the project template once the project has code (a stub before then would only say "no code yet"): short project instructions (stack, commands, where to read), linking to the root `AGENTS.md` instead of repeating it.
  Harnesses load the instructions nearest the files being edited, so an agent working in a project gets the root rules and the project's own.
- `specs/`: its specs, named `SPEC-YYYY-MM-DD-slug` like every spec and ranked in the one `specs/PRIORITIES.md`, whose rows link into the project.
- `docs/decisions/`: its decision records, in the usual format.
- The code, tests, and anything else the project needs.

What applies to the whole repo stays at the root: `AGENTS.md`, `docs/decisions/` (conventions, structure, model roles, toolchains, this record), `specs/PRIORITIES.md`, and specs that aren't one project's (such as the harness, eval pages, and scaffold).
Root decisions apply to every project.
A project records its own decision when a choice is its alone, or when it departs from a root decision within the project, naming the record it departs from.

Shared agent skills live in `skills/<name>/`.

### Starting anew

- The old repo is a reference only: read it for behavior, tests, and lessons, but don't copy its history or its decision records.
  Rebuild from the spec, test first.
- Each project's first decision record chooses its stack, citing the old repo's choice and whether it still holds.
- Old specs and acceptance criteria can be carried into the new spec, rewritten in this repo's format.
- A project's spec is `Done` when the rebuild meets its definition of done; JC then points the old repo's README here and archives it.

### Latest models

- Any LLM feature picks its model by role (such as `cheap` or `frontier`) through the model roles config from SPEC-2026-09-26-vendor-neutral-ai-harness, never a model ID in code, so moving to a newer model is a config change.
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

Colocated over parallel trees (`projects/<slug>/`, `specs/<slug>/`, `docs/decisions/<slug>/`): one folder holds everything about a project, its nested `AGENTS.md` (once it has code) points agents at its specs and decisions without their knowing a repo-wide convention, and a project can be extracted in one move.
The cost is that specs are no longer all under `specs/`; the priority table is the index.

All decisions at the root instead: fine for a few projects, but most records would be stack choices only one project cares about.

### Dependencies

[SPEC-2026-09-30-projects-scaffold](../../specs/SPEC-2026-09-30-projects-scaffold.md) sets up the layout, toolchains, and per-project CI; projects started before it lands, like the stock screener, adopt it then.

### Interfaces

## Key Results and retrospective feedback
