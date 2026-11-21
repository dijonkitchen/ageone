# SPEC-2026-11-21-first-mate: A First Mate per Project, Run From the Phone

Builds what [Open Cloud Agents from Mobile](../docs/decisions/2026-11-18-open-cloud-agents.md) recommends: sandboxed agent threads on a small always-on VM ("the box"), steered from the T3 Code phone app, with one coordinating thread per project, the first mate, in the role Claude Code Projects' coordinator plays.

T3 Code already delegates threads, watches pull requests, and runs scheduled tasks, and its pi threads get those tools too (`docs/orchestration-v2/orchestrator-mcp-server.md` in its repository).
So this spec adds no service: it is a bootstrap script for the box, a role prompt for the first mate, a memory convention, and checks that the whole loop works on GitHub and on Forgejo.

## Functional requirements

### The box

- `box/bootstrap` turns a fresh Debian or Ubuntu VM (x86_64 or arm64) into the box, and running it again changes nothing.
  It installs and pins: Tailscale, T3 Code as a background service (`t3 service install`), pi at the version in `harness/models.json`, `gh`, Forgejo's `fj`, and this repository's environment (`make`).
  T3 Code's version is pinned in `harness/models.json` under `harnesses`, next to pi's.
- T3 Code and every agent run as one unprivileged user that owns nothing of JC's beyond the box's own tokens.
  The box is the sandbox: worker threads run in full-access mode inside it, each in its own git worktree.
- The phone reaches the box only over Tailscale HTTPS (`t3 serve --tailscale-serve` or `t3 up` with Tailscale).
  No public port, and T3 Connect stays off.
- Secrets never live in the script or the repository: the model key and git tokens go into T3 Code's settings or secret cards, or a mode-600 environment file on the box.
- `box/check` reports the installed versions against the pins, the T3 service state, the Tailscale address, and whether pi on the box reaches the gateway.

### Models and harnesses

- pi on the box uses this repository's harness settings (`harness/sync --agent-dir` for the agent user), so every request goes through the active gateway with zero data retention, and the gateway extension loads once the repository folder is trusted in pi.
- The first mate runs on the `cheap` role at low effort; worker threads default to the `default` role, and use `frontier` when JC or the first mate asks for it.
- Other harnesses (OpenCode, Codex, Claude Code) can be installed by the same script behind a flag and picked per thread; none is required.

### The first mate

- `skills/first-mate/SKILL.md` holds the role prompt, written so any harness can follow it; the parts that name T3 Code's tools sit in one section so a client swap edits only that section.
- One pinned thread per T3 Code project starts from that skill.
  For each message from JC it either answers in place, starts a worker thread, or sends a follow-up to the worker thread already on that area, and says which.
- Worker threads start with `delegate_task` in their own worktree (`isolation: "worktree"`), on the provider and model the role calls for.
  A child thread sees only its task prompt, so the first mate writes each prompt with the goal, the relevant project memory, the branch and pull request conventions, and what needs JC's go-ahead.
- The first mate watches each pull request its workers open (`watch_pull_request`; child threads can't watch), routes failed checks, review comments, and conflicts back to the worker, and tells JC when a pull request is ready or needs a person.
- Recurring work JC asks for becomes a T3 scheduled task (`schedule_task`) that posts into the first mate's thread.
- It asks before steps that can't be undone (merging, deleting, anything sent outside the project) and otherwise proceeds and reports.

### Memory

- Project memory lives in a private git repository on the box's git host, one folder per project, each with a `MEMORY.md` index and one Markdown file per subject.
  It never goes into a public repository.
- The first mate reads the index at the start of each turn it needs it, writes what a later thread would otherwise have to ask JC, and commits and pushes each change.

### Git hosts

- GitHub: a fine-grained token limited to the chosen repositories, with an expiry of 90 days or less and only the permissions threads need (contents, pull requests, and issues read and write; actions and commit statuses read; workflows only if threads edit CI files), given to T3 Code and `gh`.
  GitHub lists the Checks API as a known limitation of fine-grained tokens, so item 5 confirms that pull request watching still sees check results.
- Forgejo or Codeberg: a repository-scoped access token (Forgejo 15.0 or later) for `fj` and git over HTTPS.
- `box/README.md` lists how to create, scope, rotate, and revoke each.

## Non-functional requirements

- No new service or long-running code of our own; if the loop can't work without one, stop and revisit the decision record (Omnara self-hosted is the named fallback).
- Reproducible: from a fresh VM to a paired phone in under 30 minutes of JC's time, by following `box/README.md`.
- Portable: moving the box to another host, or T3 Code to another client, is a re-run of `box/bootstrap` plus re-pairing; memory and the skill carry over unchanged except the skill's client section.
- Private by default: gateway zero data retention, Tailscale only, no public ports, no plugin or skill marketplaces.
- Fixed cost of $10 a month or less before model spend.

## Definition of done

1. `box/bootstrap`, `box/check`, and `box/README.md` exist; on a real VM, recorded in the pull request with its host, size, and monthly price, a fresh run then a second run both pass `box/check`, and the second changes nothing.
2. A phone pairs over Tailscale and starts a pi thread on this repository; it runs on the `default` role through the gateway with zero data retention (shown by the gateway's logs or response) and opens a pull request on GitHub from the app.
3. The same works on a Forgejo or Codeberg repository: clone, commit, push, and a pull request through `fj`, with a repository-scoped token.
4. From the first mate thread, one message with three tasks becomes three worker threads in their own worktrees; a follow-up reaches the right worker; a quick question gets an answer in place; each result comes back to the first mate.
5. A worker's pull request with a failing check wakes the first mate, which gets the worker to fix it, and the fix turns the check green.
6. A scheduled task made by the first mate runs on time and posts into its thread.
7. A preference JC tells the first mate lands in the memory repository and shows up in a later worker's task prompt.
8. For the threads in items 2 to 6, the pull request records T3 Code's estimated cost and the gateway's billed cost per thread.
9. One week of JC's real tasks runs through the first mate alongside Claude Code Projects, and the decision record's Key Results compare them by cost per merged pull request, pass rate, and JC's own estimate of minutes spent.
10. The decision record is amended with anything the build changed, and `specs/PRIORITIES.md` shows this spec as `Done`.
