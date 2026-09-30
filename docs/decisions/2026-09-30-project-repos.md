# Decision Record 2026-09-30: Project Repos

## Status timeline

2026-09-30: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Plan and prioritize work on JC's other active projects (connect, og_trail, simplefit, Fite, exp) from this repo's one priority table, without moving their code yet.

#### Non-functional

Keeps the [Structure](2026-09-25-structure.md) and [Conventions](2026-09-26-conventions.md): one `specs/PRIORITIES.md`, spec numbers unique across the repo.

### Nice to haves

#### Functional

Each project's next step exercises this repo's own agentic work, such as the eval runner from [SPEC-0002](../../specs/SPEC-0002-vendor-neutral-ai-harness.md), where that fits.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Merging the projects into this monorepo, which mixes Python, TypeScript, and plain JavaScript toolchains ([Structure](2026-09-25-structure.md) avoids multi-language monorepo structure unless it's really needed).

#### Non-functional

## Decision

A spec here may target a project that lives in its own repo.
Such a spec names its repo under a `## Repo` section, and the work (code, tests, the project's own specs and ADRs) lands in that repo, following that repo's rules.
The spec and its status stay here, in `specs/PRIORITIES.md`.

Only projects with recent original work get specs.
Forks of upstream libraries (aleph, bidi, buddy-sign, compression, and similar) and dormant repos don't.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Specs here, code there: one table ranks all work, but a project's spec and its code are in different repos, so a pull request in the project repo should link the spec here.

Revisit if a project starts sharing code with this repo, such as calling the SPEC-0002 runner as a library; that is the point to move it in under a project folder.

### Dependencies

### Interfaces

## Key Results and retrospective feedback
