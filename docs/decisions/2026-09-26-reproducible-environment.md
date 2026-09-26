# Decision Record 2026-09-26: Reproducible Environment

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

2026-09-26: Accepted by JC

2026-09-26: Amended by Claude, at JC's request: `make` alone installs Nix and devenv if missing and sets everything up idempotently.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

One command gives every person, agent, CI job, and eval sandbox the same tools at the same versions, starting with Node.js 22.19+ for pi ([SPEC-0002](../../specs/SPEC-0002-vendor-neutral-ai-harness.md)).

Security patches arrive quickly, but only through a reviewable change that the evals gate.

A bug seen once can be reproduced from what is committed.

#### Non-functional

Deterministic: pinned by a lockfile, not by whatever a package manager serves today.

Simple enough for people to use daily, not only for CI.

### Nice to haves

#### Functional

Automated update PRs from Renovate.

The eval sandbox image built from the same pins as the dev shell.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Packaging fast-moving npm tools (pi, its extensions) in Nix. `package-lock.json` pins them.

Writing our own Nix modules or overlays before a package is actually missing.

#### Non-functional

## Decision

Use [devenv](https://devenv.sh) (Nix underneath) for the environment, with nixpkgs on `nixos-unstable`.

- `devenv.nix` declares the tools, `devenv.yaml` the inputs, and `devenv.lock` pins every input by commit and hash. `make` installs Nix and devenv if missing, builds it, and checks it; see [SPEC-0003](../../specs/SPEC-0003-make-setup.md).
- `nixos-unstable` instead of devenv's default `cachix/devenv-nixpkgs/rolling`: security fixes arrive sooner, and our evals test each bump instead of devenv's testing.
- npm packages stay pinned by `package-lock.json`, not Nix: nixpkgs lags or lacks fast-moving npm tools.
- Updates: `make update` (`devenv update`) on a weekly schedule, opened as a PR, merged only if `make check` and the evals pass. One lockfile diff per bump.
- Eval sandbox: build it with `devenv container build` once `evals/` exists, so the image is determined by `devenv.lock`.

### Reproducible bugs

Nix pins the build, not the run. A bug is reproducible from these together:

- `devenv.lock` and `package-lock.json`.
- The model that actually served each call, its exact ID, and the OpenRouter host (hosts can differ in quantization).
- Recorded web search and fetch results, since live results change.
- pi's session JSONL, which is also the raw material for eval cases.

### High-level C4(context/container/component/code) diagram

```
devenv.yaml + devenv.lock ──> devenv ──> dev shell (people, agents, CI)
package-lock.json ──────────────┘   └──> container image (eval sandbox)
weekly `make update` PR ──> `make check` + evals ──> merge
```

### Choices and Tradeoffs/Risks

- devenv over a plain flake: short config, tasks, tests, git hooks, and containers built in, with full Nix still available inside `devenv.nix`. Costs one more tool with its own releases; pin it.
- devenv over Devbox: one nixpkgs pin for everything (one glibc, one openssl) and a sandbox image built by Nix. Devbox pins each package separately through Jetify's Nixhub service, which can mix nixpkgs commits, and exports a Dockerfile-built image. Devbox needs no Nix knowledge and has Renovate support today.
- Nix over Docker with apt: `apt-get update` builds something different every week; Nix builds the same thing from the same lock.
- Guix: stronger bit-for-bit reproducibility and grafts for fast core-library fixes, but a smaller package set and Linux only.
- Wolfi and Chainguard images: fastest CVE turnaround, but they only build containers. Revisit for the eval sandbox if it has to hold zero known CVEs, for example when it runs untrusted code from the web.
- Risk: Renovate can't update `devenv.lock` yet. Its `nix` manager only matches `flake.nix` and always updates a sibling `flake.lock`. Support is in [renovatebot/renovate#40060](https://github.com/renovatebot/renovate/pull/40060), a draft blocked on devenv support in Renovate's tool images, [containerbase/base#7373](https://github.com/containerbase/base/pull/7373). As of 2026-09-26 that PR is open and in review; a token-handling helper it depends on, [containerbase/base#7425](https://github.com/containerbase/base/pull/7425), merged 2026-09-21. Until both land, a scheduled CI job runs `make update` and opens the PR. Renovate still updates `package-lock.json`.
- Risk: some bumps of core libraries take a week or more to reach `nixos-unstable`. Accepted: the lock still moves as a whole and is tested.

### Dependencies

Nix and devenv, installed by `make` if missing (Nix through NixOS's official installer at `artifacts.nixos.org/nix-installer`, which asks before using sudo). Network access to GitHub archives and cache.nixos.org.

### Interfaces

- `devenv.nix`, `devenv.yaml`, `devenv.lock`.
- `make`, the one command people and agents need. Other `Makefile` targets are for debugging and maintenance.

## Key Results and retrospective feedback

To be filled after the first weekly update PR and the first eval sweep in the devenv container.
