# Decision Record 2026-11-18: Open Cloud Agents from Mobile

## Status timeline

2026-11-18: Proposed by Claude, at JC's request

## Objective Context

JC asked for open options to recreate cloud agents driven from a native phone app: sandboxed agents, the most cost-effective harness and models, agnostic to both, on GitHub or personal git repositories, without lock-in.
JC then added: match or exceed Claude Code Projects, with a "first mate" per project.
Facts below were checked on 2026-11-18 unless a source gives another date; see [Sources](#sources).

### Simple, lovable, complete must haves

#### Functional

Start, steer, and review agent threads from a native iOS or Android app, with work continuing while the phone and laptop are off.
A first mate per project: one coordinating conversation that turns requests into threads, keeps project memory, says what needs JC, and follows pull requests, as Claude Code Projects does.
Works on GitHub repositories and on personal git hosts (Forgejo, Codeberg, or a plain SSH remote).
Any harness and any model per thread, chosen by cost per passed task.

#### Non-functional

No layer that only one vendor can run; each layer swaps with a config change or a re-run of a setup script.
Agents never run on JC's own computers by default, and each thread's git credentials are scoped to its repositories and expire.
Private by default: the zero data retention rules in [Model Gateway](2026-11-12-model-gateway.md) still apply.
Fixed cost under $10 a month before model spend.

### Nice to haves

#### Functional

Exceed Claude Code Projects where it is closed: models from any vendor, cost per thread visible, persistent workspaces that don't lose uncommitted work, any git host, and evals that gate harness and model changes.
Push notifications and voice.

#### Non-functional

Self-hostable end to end, so a vendor closing its source or raising prices costs a re-run of setup, not a rewrite.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Building our own phone app, agent harness, or sandbox runtime.
Multi-user features before the single-user loop works.

#### Non-functional

Kubernetes or a fleet of machines for one person's projects.
Plugin and skill marketplaces as a source of code that runs with agent credentials.

## Decision

Six layers, each replaceable on its own, assembled from open source parts.
Only the first mate needs new glue, and that waits for a spec ([spec first](#next-step)).

| Layer | Pick now | Warm alternative | Swap cost |
|-------|----------|------------------|-----------|
| Phone app and threads | [T3 Code](https://github.com/pingdotgg/t3code) (MIT) over Tailscale | [Happier](https://github.com/happier-dev/happier) (MIT), [Paseo](https://github.com/getpaseo/paseo) (Apache-2.0) | Install another client on the same box; harness sessions stay on disk |
| First mate | A coordinator thread per project on the `cheap` role, driving worker threads through T3 Code's MCP server | [Omnara](https://github.com/omnara-ai/omnara) self-hosted (Apache-2.0) | Point the coordinator at another client's MCP (`happier mcp serve`) |
| Harness | [pi](https://github.com/earendil-works/pi), as in [Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md) | OpenCode, Codex CLI, Claude Code, any [ACP](https://agentclientprotocol.com) agent, picked per thread | Pick another provider in the thread |
| Sandbox | One always-on small VM as "the box" | MicroVM per project or thread: [E2B runtime](https://github.com/e2b-dev/runtime) self-hosted (Apache-2.0) or [Sprites](https://fly.io/sprites) hosted | Re-run the bootstrap script on another host |
| Models | Unchanged: [Model Gateway](2026-11-12-model-gateway.md) roles on Vercel AI Gateway | OpenRouter, one setting away | Already one setting |
| Git | GitHub App installation tokens; Forgejo repository-scoped tokens; SSH deploy keys | Fine-grained personal access tokens per project | Credential helper per host |

### 1. Phone app and threads: T3 Code

- Native iOS and Android apps, plus desktop and web, all showing the same projects and threads from one server.
- Runs Claude Code, Codex, Cursor, OpenCode, and pi natively (`packages/provider-pi`), plus any ACP agent.
- Each thread can get its own git worktree; diffs, commits, pushes, and pull requests from the app.
- Runs headless on a VPS (`t3 up`, `t3 serve --tailscale-serve`), with one-time pairing per device and per-scope access.
- Outside agents reach it through its MCP server and can list projects, start, message, wait on, and stop threads (`t3_thread_launch`, `t3_thread_wait`, `t3_thread_read`), at an access level JC approves; a thread an outside agent starts can't exceed that level.
  This is what makes a first mate possible without building a client.
- MIT, about 64,000 stars, active daily.
- Connect over Tailscale (free Personal plan, non-commercial, up to 6 users), not T3 Connect, whose relay's encryption and self-hosting aren't documented.
  Tailscale's control server is closed; [Headscale](https://github.com/juanfont/headscale) (BSD-3-Clause) is the self-hosted swap.

### 2. First mate: a coordinator thread per project

Each project gets one long-lived thread, on the `cheap` role at low effort, that JC talks to from the phone.
It reads the project's instructions and memory, turns requests into worker threads through T3 Code's MCP tools, waits on them, and reports back.
Workers run on the `default` role, or `frontier` when asked.
Around it, small scripts on the box that the spec will define:

- Memory and instructions are Markdown files in a private git repository, one folder per project, with a `MEMORY.md` index, so memory is versioned, reviewable, and readable by any harness.
- Schedules are systemd timers that message the first mate or start a thread.
- A pull request watcher (webhook or a timer calling `gh` or Forgejo's API) sends CI failures and review comments to the thread that opened the pull request.
- Thread states for an overview (working, waiting on JC, ready for review, landing, resolved) come from T3 thread status plus pull request status.
- Decisions JC must make arrive as questions in the thread; ACP stabilized structured form elicitation on 2026-07-22, which clients can render as choices.

### 3. Harness: pi by default, any harness per thread

Same-model comparisons agree that the harness moves cost far more than pass rate, and pi was the cheapest per pass in both runs that included it:

| Source | Model | pi | OpenCode | Codex | Claude Code |
|--------|-------|----|----------|-------|-------------|
| [RUNTA FrontierHarness](https://runta.com/blog/introducing-frontierharness-eval/) (2026-09-01; vendor-run, 30 tasks, one attempt each) | Kimi K3 | 60.0%, $2.43 per pass | 50.0%, $3.24 | 66.7%, $3.47 | 63.3%, $18.34 |
| [Tensorlake](https://www.tensorlake.ai/blog/best-ai-coding-agents-2026) (2026-08-13; blog, 30 tasks; pi arm mostly on DeepSeek's own API) | DeepSeek V4 Flash | 66.7%, $0.028 per success | 46.7%, $0.073 | 53.3%, $0.081 | 53.3%, $0.195 |

[What Does a Harness Buy? Tokens, Mostly](https://arxiv.org/abs/2610.04433) (arXiv, 2026-10-03) finds up to 3x cost spread across Claude Code, mini-SWE-agent, and OpenCode on SWE-bench Verified with pass rates within 5 points, and that swapping harness flips about as many hard tasks as rerunning the same one.
The evidence is thin (one vendor-run benchmark, one blog), so this repo's evals stay the judge; `evals/run` already takes the harness as a setting.
Threads that pick Claude Code or Codex run those vendors' own CLIs, so they can sign in with JC's Claude or ChatGPT plan, with only that vendor's models (and, for Claude Code, the highest cost per pass above).

### 4. Sandbox: the box first, microVMs when a spec needs them

Model spend dominates cost per passed task, so sandboxes are chosen for persistence, openness, and idle behaviour, not rate.
A 20-minute thread on 2 vCPU and 4 GiB, with the CPU about 10% busy while waiting on the model (Sprites billed on 2 GB actually used), costs at list rates:

| Option | Open source | Isolation | Rates | Idle | 20-minute thread |
|--------|-------------|-----------|-------|------|------------------|
| Always-on VM: Hetzner CX23 (Germany or Finland) or Fly Machine shared-cpu-1x 1 GB (US) | Any Linux host | VM | €5.49 a month (new orders since 2026-06-15); $6.70 a month | Always billed | Fixed |
| [Fly Sprites](https://fly.io/sprites) | No (SDKs MIT) | Hardware-isolated VM | $0.0385 per CPU-hour used, $0.021875 per GB-hour used | Sleeps when idle; an open TCP connection keeps it awake | About $0.017 |
| [Cloudflare Containers](https://developers.cloudflare.com/containers/pricing/) | No | Container | $0.072 per vCPU-hour active, $0.009 per GiB-hour; Workers Paid $5 a month | Sleeps after a timeout | About $0.030 (2 vCPU, 8 GiB shape) |
| [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox/pricing) | No | Firecracker | $0.128 per active CPU-hour, $0.0212 per GB-hour; Hobby includes 5 CPU-hours, 45-minute sessions | Memory bills while running | About $0.037 |
| [E2B](https://e2b.dev/pricing) | Runtime Apache-2.0; self-hosts on one KVM host ("Embed") | Firecracker | $0.0504 per vCPU-hour, $0.0162 per GiB-hour; Hobby sessions 1 hour, Pro $150 a month | Auto-pauses, resumes on traffic | About $0.055 |
| [Modal](https://modal.com/pricing) | No | Not stated on pricing page | $0.1419 per core-hour (2 vCPU), $0.024 per GiB-hour; $30 a month free credit | Bills max(request, usage) | About $0.079 |
| Daytona | No: went closed source in June 2026, repository archived | | Same rates as E2B | | About $0.055 |

For comparison, a passed task on real repositories cost $1.13 to $1.76 on DeepSeek V4.1 Flash and $5.14 to $25.80 on Opus 5.5 in FrontierCode 2.0 (checked 2026-11-12), so a sandbox is a few percent of a task.

Start with the box: one small always-on VM that holds T3 Code, the harnesses, the first mates, and the worktrees, built from one bootstrap script (`make` plus T3 Code and Tailscale), with agents as an unprivileged user and nothing of JC's own on it.
It is the cheapest fixed cost, keeps first mates reachable for schedules and webhooks, and moves to any Linux host.
Move a project or a thread into a microVM when the spec calls for stronger isolation or parallel heavy builds:

- Self-hosted: the E2B runtime, the only option with the same stack hosted and self-hosted, needs Linux with KVM.
  Hetzner Cloud VMs lack nested virtualization; Hetzner dedicated servers and AWS C8i, M8i, and R8i (nested virtualization since 2026-02-16) have it.
  [microsandbox](https://github.com/superradcompany/microsandbox) (Apache-2.0, libkrun) and Earendil's [Gondolin](https://github.com/earendil-works/gondolin) (Apache-2.0, experimental, keeps real secrets on the host and gives the VM a placeholder) are lighter options, and Gondolin already has a pi extension.
  [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) (Apache-2.0, v1.0.2) fits only if Kubernetes arrives for another reason.
- Hosted: Sprites, for a persistent per-project VM that sleeps when idle and keeps credentials out through its connectors.

### 5. Models: unchanged

Roles, gateway, and zero data retention stay as decided in [Model Gateway](2026-11-12-model-gateway.md); T3 Code runs pi with the repository's `.pi/settings.json` when the thread's folder is this repository.

### 6. Git: short-lived, repository-scoped credentials on every host

- GitHub: a GitHub App owned by JC, installed on chosen repositories, with its private key on the box outside any agent's reach; a helper mints an installation token per thread, limited to that thread's repositories and to contents and pull request permissions.
  Installation tokens last one hour and, since 2026-10-02, are about 520 characters, so treat them as opaque strings.
- Forgejo or Codeberg: repository-scoped access tokens (Forgejo 15.0 and later) limited to `read:repository`, `write:repository`, and issue scopes; they can't do repository administration.
- Plain SSH remotes: one deploy key per repository.
- Pull request and review calls go through `gh` for GitHub and Forgejo's REST API, behind one small adapter the first mate uses.

### Compared with Claude Code Projects

From the [Projects docs](https://code.claude.com/docs/en/claude-projects) (public beta on Pro, Max, and Ultra):

| Capability | Claude Code Projects | This proposal |
|------------|----------------------|---------------|
| Phone app | Claude app (iOS, Android) | T3 Code app (iOS, Android), MIT |
| Coordinator and threads | Built in; coordinator posts status on its own | First mate thread plus T3 threads through MCP; glue to build |
| Models | Anthropic only; Opus at high effort by default | Any model per role, picked by cost per passed task |
| Harness | Claude Code | pi by default; OpenCode, Codex, Claude Code, or any ACP agent per thread |
| Repositories | GitHub, plus uploaded files | Any git remote: GitHub, Forgejo, Codeberg, SSH |
| Workspace | Cloud sandbox paused between turns; if it can't resume, the thread restarts from a fresh clone and uncommitted changes can be lost | Persistent box; microVM snapshots later |
| Memory | Project memory files and instructions in project settings | Markdown in a private git repository: versioned and portable |
| Pull requests | Watches and auto-fixes CI and review comments | To build: webhook or timer messages the thread |
| Schedules | Cloud scheduled tasks | systemd timers on the box |
| Overview, decision cards, library | Built in | Thread list and push from T3; states and decisions to build |
| Connectors (Gmail, Drive, and so on) | Built in | MCP servers per harness, set up by hand |
| Cost | Plan limits, used faster than single sessions; 500 new threads a day | About €6 a month plus models at cost; cost per thread visible |
| Sharing | One user | One user now; T3 Code and Happier support more later |

Where Claude Code Projects stays ahead: no setup or upkeep, polish, built-in pull request auto-fix, and connectors.
So keep using it while the first mate is built, then compare both on the same week of real tasks by cost per merged pull request and minutes of JC's attention.

### High-level C4(context/container/component/code) diagram

```mermaid
flowchart LR
  phone["Phone: T3 Code app"] -- "Tailscale" --> t3
  subgraph box["The box: small always-on VM"]
    t3["T3 Code server"]
    mate["First mate thread per project (pi, cheap role)"]
    workers["Worker threads (pi, OpenCode, Codex, Claude Code), one worktree each"]
    glue["Glue: schedules, pull request watcher, token helper"]
    t3 --- mate
    mate -- "MCP: launch, message, wait" --> workers
    glue --> mate
  end
  workers -- "roles, zero retention" --> gateway["Model gateway: Vercel, OpenRouter one setting away"]
  workers -- "short-lived scoped tokens" --> git["GitHub, Forgejo, SSH remotes"]
  git -- "webhooks or polling" --> glue
  workers -. "later" .-> microvm["MicroVM per project or thread: E2B runtime or Sprites"]
```

### Choices and Tradeoffs/Risks

Phone clients considered (all run agents on a machine you connect, not in their own cloud):

| Client | License | Stars | Native apps | Harnesses | Connection | Orchestration |
|--------|---------|-------|-------------|-----------|------------|---------------|
| T3 Code | MIT | 64k | iOS, Android, desktop, web | Claude Code, Codex, Cursor, OpenCode, pi, any ACP | LAN, Tailscale, T3 Connect | Projects and threads; MCP for outside agents |
| Happy | MIT | 25k | iOS (Swift), Android (Kotlin) | Claude, Codex, Grok; OpenCode or any ACP | End-to-end encrypted relay | Subagent delegation; multiplayer |
| Paseo | Apache-2.0 (site) | 24k | iOS, Android, desktop, web | Claude Code, Codex, Copilot, OpenCode, pi, more through ACP | Encrypted relay, LAN, Tailscale | Agents launch agents; voice |
| Happier | MIT | 2.2k | iOS, Android, desktop, web | 13 including pi, any ACP | Encrypted relay you can self-host | `happier mcp serve` creates sessions; push inbox; voice |
| OpenCode Mobile | MIT | 0.3k | Android | OpenCode | Tailscale | None |

T3 Code over Happier: its projects-and-threads model maps onto Claude Code Projects, its MCP has permission ceilings for outside agents, and its community is the largest.
Happier is the fallback if T3 Code stalls: it has the self-hostable encrypted relay and push inbox T3 lacks.
Closed clients (Claude app, ChatGPT's Codex remote, Maude, Cosyra, Vicoa) were ruled out for lock-in.

First mate options considered:

- T3 Code MCP plus a pi coordinator (chosen): least glue, same app as the threads.
- Omnara self-hosted (Apache-2.0): a full managed agent platform (REST API, Postgres state, schedules, memory, subagents, 12 sandbox providers or your own machines, Slack and Discord, open source mobile app), but its own agent loop rather than pi or ACP harnesses, Postgres and Redis to run, and a product that pivoted in January 2026.
  Switch to it if the glue grows past a few hundred lines.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) (MIT, 264k stars): personal agent with 20+ messaging gateways (Telegram, Discord, Slack, Signal, email), cron, memory, subagents, and terminal backends (local, Docker, SSH, Daytona, Modal, Vercel Sandbox).
  A good first mate if JC prefers a chat app to a coding app, but it passed 50% in RUNTA's coding run, so it should hand coding to pi threads.
- [pi-chat](https://github.com/earendil-works/pi-chat): Discord and Telegram to sandboxed pi, a Gondolin VM per channel, memory files; 16 commits, early.
- [open-inspect/background-agents](https://github.com/open-inspect/background-agents) (MIT): Cloudflare control plane, Modal, Daytona, or E2B sandboxes, OpenCode or Claude Agent SDK, web, Slack, GitHub, and Linear clients, multiplayer; no phone app or coordinator, and it caches git credentials on disk where snapshots keep them.
- OpenHands (MIT): issue to pull request in a Docker sandbox; no coordinator.
- Not chosen: OpenClaw (341 malicious skills among 2,857 audited on ClawHub, and CVE-2026-25253, a one-click remote code execution), and Vibe Kanban (its company shut down in 2026 and handed it to the community).

Risks:

- T3 Code is young and gates contributions; its pi provider with this repo's gateway extension, and an MCP-driven coordinator running as a T3 thread, are unverified and are the spec's first spike.
- One box means one blast radius: a prompt-injected thread can read other projects' worktrees.
  Short-lived tokens limit what it can push; a Linux user or microVM per project is the next step.
- Providers close or reprice: Daytona went closed source in June 2026, and Hetzner raised CX and CAX prices about 30% to 38% and CPX and CCX up to 2.7x on 2026-06-15.
  Keeping the box reproducible from one script keeps a move cheap.
- Sprites' idle rules are documented inconsistently and a restart after waking is reported, so test before relying on them.
- E2B's self-hosted runtime is not documented as SDK-compatible with E2B's cloud; verify before counting on one SDK for both.
- Same-model harness results come from one vendor benchmark and one blog; our evals decide.

### Dependencies

[Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md), [Model Gateway](2026-11-12-model-gateway.md), [Reproducible Environment](2026-09-26-reproducible-environment.md), and the evals in [`evals/`](../../evals/README.md).

### Interfaces

- Thread control: T3 Code MCP tools (`t3_thread_launch`, `t3_thread_wait`, `t3_thread_read`); Happier's `happier mcp serve` as the fallback.
- Harness: any provider T3 Code runs natively, or any ACP agent.
- Models: `harness/models.json` roles.
- Git: `git` with a credential helper that hands out short-lived tokens; one adapter for pull request calls (`gh` or Forgejo REST).
- Box: one bootstrap script, so any Linux host with network access can become the box.
- Memory: Markdown with a `MEMORY.md` index in a private git repository.

## Next step

If accepted, write `SPEC-2026-11-18-first-mate` before any code: the box bootstrap, a spike on T3 Code with pi and an MCP-driven coordinator, the pull request watcher, schedules, the token helper for GitHub and Forgejo, and a definition of done that includes the week-long comparison with Claude Code Projects.

## Key Results and retrospective feedback

## Sources

- Claude Code Projects: https://code.claude.com/docs/en/claude-projects
- T3 Code: https://github.com/pingdotgg/t3code, and its `docs/user/remote-access.md` and `docs/user/outside-agents.md`
- Happy: https://github.com/slopus/happy; Happier: https://github.com/happier-dev/happier; Paseo: https://paseo.sh/claude-code; OpenCode Mobile: https://github.com/dzianisv/opencode-mobile
- Phone client comparison (published by Maude, one of the apps, updated 2026-10-30): https://maude.pilotdev.fr/compare/coding-agent-phone-apps/
- Omnara: https://github.com/omnara-ai/omnara; Hermes Agent: https://hermes-agent.nousresearch.com/docs; pi-chat: https://github.com/earendil-works/pi-chat; open-inspect: https://github.com/open-inspect/background-agents
- pi: https://github.com/earendil-works/pi; Gondolin: https://github.com/earendil-works/gondolin; OpenCode server: https://opencode.ai/docs/server/
- ACP updates (registry, transports working group, elicitation): https://agentclientprotocol.com/updates.md
- Harness costs: https://runta.com/blog/introducing-frontierharness-eval/, https://www.tensorlake.ai/blog/best-ai-coding-agents-2026, https://arxiv.org/abs/2610.04433
- Sandbox prices: https://e2b.dev/pricing, https://vercel.com/docs/vercel-sandbox/pricing, https://developers.cloudflare.com/containers/pricing/, https://modal.com/pricing, https://fly.io/sprites, https://fly.io/learn/ai-sandbox-pricing/, https://fly.io/learn/always-on-agent-hosting-cost/
- Sprites idle behaviour: https://docs.fly.io/sprites/working-with-sprites/, https://community.fly.io/t/sprite-restarts-by-itself-1-to-3-minutes-after-waking-from-idle-reproducible-sbd-storage/28796
- E2B runtime: https://github.com/e2b-dev/runtime; Daytona closed source: https://github.com/daytonaio/daytona (archived), https://github.com/nightona-co/nightona
- Hetzner prices: https://northflank.com/blog/hetzner-cloud-server-price-increases; nested virtualization: https://wz-it.com/en/blog/hetzner-cloud-vs-dedicated-server/, https://aws.amazon.com/about-aws/whats-new/2026/02/amazon-ec2-nested-virtualization-on-virtual
- Tailscale pricing: https://tailscale.com/pricing; Headscale: https://github.com/juanfont/headscale
- GitHub App tokens: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app, https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out/
- Forgejo token scopes: https://forgejo.org/docs/latest/user/token-scope/
- OpenClaw security: https://www.esecurityplanet.com/threats/hundreds-of-malicious-skills-found-in-openclaws-clawhub/; Vibe Kanban shutdown: https://vibekanban.com/blog/shutdown
