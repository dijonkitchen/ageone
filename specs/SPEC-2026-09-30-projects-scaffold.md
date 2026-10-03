# SPEC-2026-09-30-projects-scaffold: Projects Scaffold

Set up the monorepo so projects can restart here, as decided in [Projects in ageone](../docs/decisions/2026-09-30-projects-in-ageone.md).

## Functional requirements

- `projects/` and `skills/` exist, each with a short `README.md` saying what goes there.
- `devenv.nix` provides the two project toolchains: Bun for TypeScript and plain JavaScript, and Python with uv.
  `make` sets them up and its check proves both work.
- A project template: copying `projects/_template/` gives an `AGENTS.md` with `CLAUDE.md` symlinked to it, `specs/`, `docs/decisions/` with a first decision record stub, and a `Makefile` with `check` (lint, format, typecheck where the language has one, tests).
- CI runs `make check` in each project folder that changed in a pull request, and in all of them on `main`.
- `make new PROJECT=<slug>` copies the template into `projects/<slug>/`.
- `make links` also repairs each project's `CLAUDE.md -> AGENTS.md` symlink.

## Non-functional requirements

- Simple: plain Makefiles per project, no cross-language build system.
- Deterministic: toolchain versions are pinned by `devenv.lock`; each project commits its lockfile.
- Fast: a pull request that touches one project runs only that project's checks.

## Definition of done

1. The folders and template are committed, and `make new PROJECT=example` creates a project whose `make check` passes.
2. `make` from a fresh clone sets up Bun and uv and checks both.
3. CI runs only the changed project's checks on a pull request, shown with a test pull request.
