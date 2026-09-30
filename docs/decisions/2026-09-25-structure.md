# Decision Record 2026-09-25: Structure

## Status timeline

2026-09-25: Proposed by JC

2026-09-25: Accepted by JC

2026-09-26: Amended by JC: `/docs/decisions/` holds any decision records, not only architectural ones.

2026-09-30: Amended by Claude, at JC's request: projects live in `/projects/<slug>/`, with specs in `/specs/<slug>/` and decision records in `/docs/decisions/<slug>/`; see [Projects in ageone](2026-09-30-projects-in-ageone.md).

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
`/projects/<slug>/`: the code of each project in the monorepo ([Projects in ageone](2026-09-30-projects-in-ageone.md)).
`/skills/`: shared agent skills.
`/docs/decisions/`: Any decision records (ADRs), especially architectural decision records, for the projects in the monorepo.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

### Dependencies

Project needs and best practices.

### Interfaces

## Key Results and retrospective feedback
