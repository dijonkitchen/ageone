# Decision Record 2026-09-25: Structure

## Status timeline

2026-09-25: Proposed by JC

2026-09-25: Accepted by JC

2026-09-26: Amended by JC: `/docs/decisions/` holds any decision records, not only architectural ones.

2026-09-30: Amended by Claude, at JC's request: each project lives in `/projects/<slug>/`, with its own `AGENTS.md`, `specs/`, and `docs/decisions/`; see [Projects in ageone](2026-09-30-projects-in-ageone.md).

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Simple, readable, and easily understandable (by people and agents) folder and file structure.

#### Non-functional

### Nice to haves

#### Functional

One battle-tested, reliable, common tool for them all.

#### Non-functional

Easily refactorable for performance, while still adhering to specs.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Complicated monorepo structures across multiple languages unless really needed.

#### Non-functional

## Decision

`/specs/PRIORITIES.md`: Prioritization of the specifications in the monorepo.
`/specs/`: Specification files for the projects in the monorepo.
Broken down by subdirectories per project if needed.
`/projects/<slug>/`: each project in the monorepo, with its code, specs, decision records, and `AGENTS.md` ([Projects in ageone](2026-09-30-projects-in-ageone.md)).
`/skills/`: shared agent skills.
`/docs/decisions/`: Any decision records (ADRs), especially architectural decision records, for the projects in the monorepo.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

### Dependencies

Project needs and best practices.

### Interfaces

## Key Results and retrospective feedback
