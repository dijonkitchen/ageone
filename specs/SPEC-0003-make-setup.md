# SPEC-0003: Make Setup

## Functional requirements

One simple, discoverable entry point to set up the repo and its environment, for people and agents alike: a `Makefile` whose targets wrap devenv, as decided in [Reproducible Environment](../docs/decisions/2026-09-26-reproducible-environment.md).

- `make` (or `make help`) lists every target with a one-line description.
- `make setup` checks that Nix and devenv are installed, repairs the entry-point symlinks, and builds the pinned environment.
- `make tools` fails with install steps if Nix or devenv is missing. It does not install Nix itself, since that needs root and changes the machine.
- `make links` recreates `AGENTS.md -> README.md` and `CLAUDE.md -> AGENTS.md` when a tool has turned them into copies ([Conventions](../docs/decisions/2026-09-26-conventions.md)). It refuses to delete a copy that has edits.
- `make shell` enters the environment; `make check` runs its tests; `make update` bumps `devenv.lock`.
- The environment provides Node.js 22.19+ for pi, plus `git`, `curl`, and `jq`.

## Non-functional requirements

- Simple: the Makefile only wraps commands; what the environment contains lives in `devenv.nix`.
- Deterministic: every input is pinned in the committed `devenv.lock`.
- Safe: no target installs system software or deletes edited files.

## Definition of done

1. `devenv.nix`, `devenv.yaml`, `devenv.lock`, and `Makefile` are committed.
2. `make help`, `make tools`, and `make links` behave as above, including refusing to delete an edited copy.
3. From a fresh clone on a machine with Nix and devenv, `make setup` and `make check` pass using the committed `devenv.lock`, and `make check` fails when the environment's test fails.
