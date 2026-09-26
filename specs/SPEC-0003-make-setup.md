# SPEC-0003: Make Setup

## Functional requirements

One simple, discoverable entry point to set up the repo and its environment, for people and agents alike: a `Makefile` whose targets wrap devenv, as decided in [Reproducible Environment](../docs/decisions/2026-09-26-reproducible-environment.md).

- `make`, with no target, does everything needed, idempotently: installs Nix and devenv if missing, repairs the entry-point symlinks, builds the pinned environment, and runs its tests. A second run changes nothing.
- Nix is installed with NixOS's official installer, which shows its plan and asks before using sudo. In CI (`CI` set) it runs without asking.
- The other targets exist for debugging and maintenance, and `make help` lists them.
- `make links` recreates `AGENTS.md -> README.md` and `CLAUDE.md -> AGENTS.md` when a tool has turned them into copies ([Conventions](../docs/decisions/2026-09-26-conventions.md)). It refuses to delete a copy that has edits.
- `make shell` enters the environment; `make update` bumps `devenv.lock`.
- The environment provides the current Node.js LTS (at least 22.19, which pi needs), plus `git`, `curl`, and `jq`.

## Non-functional requirements

- Simple: the Makefile only wraps commands; what the environment contains lives in `devenv.nix`.
- Deterministic: every input is pinned in the committed `devenv.lock`.
- Safe: Nix, the only system-wide install, needs the installer's confirmation outside CI; devenv installs into the user's Nix profile; no target deletes edited files.

## Definition of done

1. `devenv.nix`, `devenv.yaml`, `devenv.lock`, and `Makefile` are committed.
2. `make` installs devenv when it is missing, calls the Nix installer when Nix is missing (with `--no-confirm` only in CI), and a second `make` reinstalls nothing.
3. `make links` repairs the symlinks and refuses to delete an edited copy.
4. From a fresh clone, `make` passes using the committed `devenv.lock`, and fails when the environment's test fails.
