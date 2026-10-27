# Decision Record 2026-10-27: Dependency updates

## Status timeline

2026-10-27: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Dependencies stay current without JC reviewing every bump.
A weekly sweep brings each update pull request up to date with `main`, waits for CI, and squash merges it only if CI passes and the update has no breaking changes.
Anything risky, or worth knowing for future work, is reported to JC instead of merged.

#### Non-functional

Update pull request titles pass the Conventional Commits check, since pull requests are squash merged.

### Nice to haves

#### Functional

Minor and patch updates are grouped per ecosystem, so a week is a few pull requests rather than dozens.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Auto-merging major versions.
A major bump is merged only after its release notes show nothing in this repo breaks; otherwise it waits for JC.

#### Non-functional

## Decision

Use Dependabot, configured in [`.github/dependabot.yml`](../../.github/dependabot.yml), on a weekly schedule.

- `github-actions` for the workflows, titled `ci(deps): ...`.
- `uv` for each project with a `uv.lock` (`mle-lab`, `stock-screener`), titled `chore(deps): ...` or `chore(deps-dev): ...`.
- The project template (`projects/_template/`) is left out: it has no lock files and its `package.json` name is a placeholder.
- Nix and devenv inputs are left out: Dependabot doesn't support them.

A weekly scheduled Claude task does the sweep and reports back in the project thread.

### Choices and Tradeoffs/Risks

Renovate also covers Nix and the template, and its onboarding pull request (#27) is open.
Dependabot was chosen because JC asked for it and it needs no third-party app.
Running both would open duplicate pull requests, so #27 should be closed if this is accepted.

### Dependencies

### Interfaces

## Key Results and retrospective feedback
