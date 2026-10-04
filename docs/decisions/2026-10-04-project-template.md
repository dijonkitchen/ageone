# Decision Record 2026-10-04: Project Template

## Status timeline

2026-10-04: Proposed by Claude, implementing [SPEC-2026-09-30-projects-scaffold](../../specs/SPEC-2026-09-30-projects-scaffold.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

One way to start a project's code in `projects/<slug>/` and one command, `make check`, that CI runs per changed project, as decided in [Projects in ageone](2026-09-30-projects-in-ageone.md).

#### Non-functional

Plain Makefiles, toolchains pinned by `devenv.lock`, and pull requests that only pay for the projects they touch.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A cross-language build system or a workspace that links projects together.

#### Non-functional

## Decision

### Template

`projects/_template/` holds what every project gets: `AGENTS.md` with `CLAUDE.md` symlinked to it, `specs/`, a stack decision record stub, and a `Makefile`.
Its `stacks/bun/` and `stacks/python/` hold each toolchain's starter files, and `make new PROJECT=<slug> [STACK=bun|python]` (default `bun`) copies the common files plus one stack, fills in `__PROJECT__`, `__PACKAGE__`, `__DATE__`, and `__STACK__`, and writes the lockfile.

The one `Makefile` runs the checks of whichever toolchains are present: Bun's when `package.json` exists, uv's when `pyproject.toml` does, so a project that later adds the other toolchain needs no new build file.

| Check | Bun (TypeScript) | Python (uv) |
|---|---|---|
| Lockfile | `bun install --frozen-lockfile` | `uv sync --locked` |
| Lint and format | Biome (`biome ci`) | Ruff (`ruff check`, `ruff format --check`) |
| Typecheck | `tsc --noEmit` | mypy, strict |
| Tests | `bun test` | pytest |

Each tool is a locked dev dependency of the project, not part of `devenv.nix`, so projects upgrade their linters on their own schedule.

### Environment

`devenv.nix` enables Bun next to Node.js and keeps Python 3.12 with uv; its test runs a line of TypeScript with Bun and a line of Python through uv.

### CI

The Projects workflow lists projects with [`projects/changed`](../../projects/changed): on a pull request, those with a `Makefile` whose folder changed; on `main`, all of them.
Changes to `devenv.*`, the workflow, or the scripts check every project, and changes to `_template/` create a Bun and a Python project and check both.
Each listed project gets its own job, which runs the root `make` (installing Nix and devenv, building the pinned environment, and testing it) and then `make check` in the project inside `devenv shell`.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Biome over ESLint and Prettier: one fast tool with no config for lint and format.

Nix and devenv in CI over `setup-bun` and `setup-uv`: slower to set up, but CI uses exactly the toolchain versions `devenv.lock` pins, and every run proves a fresh `make` still works.
If setup time becomes the bottleneck, add a Nix binary cache before reaching for unpinned setup actions.

The stock screener, started before the template, gets its own `Makefile` with lint and tests; adopting the template's format check and mypy is left to its next change, since 20 of its files predate the formatter.

### Dependencies

### Interfaces

`make check` in a project folder is the contract CI relies on; anything else in a project's `Makefile` is up to the project.

## Key Results and retrospective feedback
