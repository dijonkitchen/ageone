# Decision Record 2026-09-26: Vendor-Neutral AI Harness

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

2026-09-26: Amended by Claude, at JC's request: checked against pi's current docs. Fixed the repo link and where pi reads model config, added web search and open-weight data privacy, and noted OpenAI models on Bedrock.

2026-09-26: Amended by Claude, at JC's request: OpenRouter is the default model access, replacing direct vendor APIs.

2026-09-26: Amended by Claude, at JC's request: dropped AWS Bedrock; open-weight models from Chinese labs reach us only through an allowlist of US and EU hosts on OpenRouter.

2026-09-26: Amended by Claude, at JC's request: Node.js and the eval sandbox come from the pinned devenv environment ([Reproducible Environment](2026-09-26-reproducible-environment.md)).

2026-09-27: Amended by Claude, at JC's request: the eval runner takes the harness as a setting (pi first) and has a direct mode with no harness, so [SPEC-0004](../../specs/SPEC-0004-eval-benchmark-pages.md) can compare harnesses and formats with the same metrics.

2026-09-28: Amended by Claude, at JC's request: LLM observability platforms (LangSmith, Langfuse) considered and deferred.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Use whichever model is cheapest for the job today and test the most capable one the day it ships, without rewriting anything. Judge each switch with a closed feedback loop on this repo's own tasks and data, not on public benchmarks.

#### Non-functional

Vendor neutral at every layer: harness, model access, prompts, and evals. Nothing that only one vendor's product can read.

### Nice to haves

#### Functional

One bill and one spend report across providers. Automatic fallback when a provider is down.

#### Non-functional

Immune to the bitter lesson: less scaffolding, more measurement.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Building an agent framework or a model router of our own. Running public benchmarks for their own sake. Multi-model cascades before a single-model baseline is measured.

#### Non-functional

A gateway or proxy before there is a reason (one bill, data residency, fallbacks) to run one.

## Decision

Four layers, each replaceable on its own.

### 1. Harness: pi

Use [pi](https://github.com/earendil-works/pi) ([pi.dev](https://pi.dev)) (`@earendil-works/pi-coding-agent`) as the default harness.

- Its model layer, `pi-ai`, is a unified API over many providers including Anthropic, OpenAI, Google, Azure, AWS Bedrock, Vertex, Mistral, Groq, Cerebras, Fireworks, Together, Hugging Face, NVIDIA, xAI, OpenRouter, and Vercel AI Gateway, plus any OpenAI-, Anthropic-, or Google-compatible endpoint (Ollama, vLLM, llama.cpp), and it can hand a conversation from one provider to another mid-session.
- Custom endpoints and models go in the user-level `~/.pi/agent/models.json`; `/model` switches at runtime and `pi update --models` refreshes the catalog, so a new model is usable without a release of the harness.
- Project config lives in `.pi/settings.json` (default provider and model, thinking level, enabled models, packages) and loads once the project is trusted.
- It is minimal (four tools, sub-1k-token system prompt), MIT, and scriptable: print and JSON modes, an RPC mode, and a TypeScript SDK, which is what the eval runner drives.
- Sessions are JSONL files with branching, which makes real sessions the raw material for eval cases.

Alternative kept warm: [OpenCode](https://opencode.ai), the most popular provider-agnostic harness, richer UI and IDE integration, more surface area. Because prompts and instructions live in `AGENTS.md`, `specs/`, and `docs/decisions/`, switching harness is a config change. Claude Code, Codex CLI, and Gemini CLI stay in use as vendor-specific comparison points, not as the default.

### 2. Model access: OpenRouter by default, direct when needed

- Default to [OpenRouter](https://openrouter.ai) through pi's built-in `openrouter` provider (`OPENROUTER_API_KEY`). One key and one bill for every frontier closed family (Claude, GPT, Gemini, Grok) and the largest open-weight catalog, with fallbacks across hosts. That covers every role, including a `judge` from a different vendor than the model under test.
- Privacy is set once, account-wide: zero data retention on, and the Chinese labs' first-party endpoints on the ignored providers list (section 6).
- Costs: a 5.5% fee on credit purchases, and one extra hop. Remove the fee on heavy models by bringing your own provider key (BYOK: first 1M requests a month free, then 5%).
- Go direct to a vendor's API when a native feature matters that the gateway does not pass through yet (new betas, batch APIs), or when measured spend makes the fee worth removing. Vercel AI Gateway (no markup, similar catalog, built into pi) is the fallback gateway; LiteLLM if data must stay on our infrastructure.
- Not AWS Bedrock: OpenRouter already covers its catalog (Claude, GPT, open-weight) plus Gemini, without an AWS account. Revisit only if AWS billing, IAM, or compliance becomes a requirement.

### 3. Model roles config

One checked-in, harness-neutral file (`harness/models.json`) maps roles to exact `provider/model` IDs. pi has no roles and reads `models.json` only from the user-level agent directory, so: the `default` role is mirrored into project `.pi/settings.json` (`defaultProvider`, `defaultModel`), and scripts and the eval runner pass the other roles with `pi --model <provider/model>`. A second harness gets the same file.

| Role | Purpose | Starting value (re-evaluate with evals) |
|------|---------|------------------------------------------|
| `default` | everyday agentic work | current-generation mid tier, such as `anthropic/claude-sonnet-5` |
| `cheap` | subagents, bulk, drafts | small tier or best open-weight model that passes the eval |
| `frontier` | hard tasks, escalation on failure | current top tier, such as `anthropic/claude-opus-5-5` |
| `judge` | LLM grader in evals | a different vendor from the model under test where possible |

Rules: pin exact IDs and versions in evals; prompt caching on for every role; effort tuned per role, measuring the newest model at lower effort before reaching for an older model at high effort; task budgets and max turns set on every unattended run.

### 4. Evals: a closed loop on our own tasks

Yes, evals on every switch. Without them "cheaper" and "better" are guesses.

- Cases come from real work in this repo: each completed spec or task becomes a regression case (starting state, instruction, checkable outcome); each failure becomes a new case. Aim for 10 to start, 50 within a quarter. Prefer tasks a user would plausibly give, not ones with the answer in the prompt.
- Grading is deterministic first (tests pass, file exists, diff applies, command exits 0), LLM-judge with a written rubric second, and never reference-similarity against the incumbent model's own output.
- Metrics per model per run: pass rate, cost per completed task (from API `usage`, at that model's price, cache included), tokens, turns, wall-clock, refusal rate, with 3+ repetitions and intervals. Infra errors, timeouts, and truncation go to a separate sidecar, never counted as model failures. Assert the served model on every call.
- Runner: `evals/run` drives pi in JSON or RPC mode with a fresh sandbox per case. The harness is a setting: pi first, and other harnesses (Claude Code, OpenCode) through their own print or JSON modes, each behind a small adapter that returns the same metrics. A `direct` mode calls the model through OpenRouter with no harness and no tools, for single-call cases such as reading or writing a data format. Start with a script; adopt Inspect AI or promptfoo once cases outgrow it. Both compare providers side by side and record cost and latency.
- Before trusting numbers: run the reference solutions (should pass) and a null baseline (should fail) through the grader.
- Trigger: every model change, prompt or `AGENTS.md` change, harness upgrade, and a monthly sweep of newly released models. Results are committed under `evals/results/` so the table in this record can be updated with evidence.

### 5. Web search

pi deliberately ships four tools (`read`, `bash`, `edit`, `write`), no web search, and no MCP; extensions and skills fill the gap. Native search in other harnesses is built in and maintained by the vendor: Claude's web search and fetch tools, OpenAI's web search, Gemini's Google Search grounding, and Perplexity Sonar (search plus a cited answer, a model rather than a search tool).

- Use the community extension [pi-web-access](https://github.com/nicobailon/pi-web-access) (`web_search`, `fetch_content`), declared as a package in `.pi/settings.json` so every checkout gets it. It works without a key through Exa and falls back across many backends (Brave, Tavily, Parallel, Perplexity, SearXNG, and others).
- Pin one paid backend with a key (Exa or Parallel, which lead the 2026 agent-search benchmarks) instead of the keyless default, so results and data handling are predictable.
- Risk: it is a single-maintainer community package, not vendor-backed. Pin its version, and cover it with a web-research eval case. Fallback: a small skill that calls one search API with `curl`, or the vendor harness's native search for research-heavy tasks.

### 6. Open-weight models without training on our data

Open weights do not send data anywhere; the host does. Risk comes from the host's terms, not the model's origin.

- Do not use the labs' own first-party APIs (DeepSeek, Moonshot/Kimi, Zhipu/Z.AI, MiniMax, Alibaba Qwen) for this repo's work, even though pi lists several as built-in providers. Don't store their keys.
- OpenRouter serves each open-weight model from many hosts. For Chinese-lab models that list includes the labs themselves and other China-based clouds (for example Alibaba, Baidu, SiliconFlow, StreamLake on DeepSeek V4, GLM 5.3, and Kimi K3 in September 2026), next to US hosts (Fireworks, Together, DeepInfra, Parasail, Baseten, CoreWeave, Modal) serving the same weights at the same or near price.
- Use an allowlist, not a blocklist: new hosts appear often and ownership is not always clear. Per model, pi sends OpenRouter routing fields through `openRouterRouting`: `only` set to the trusted US and EU hosts, `zdr: true`, and `data_collection: "deny"`. Quality is controlled through the allowlist (hosts that serve the model at the precision it was released in) and the eval, not a blanket `quantizations` filter: some models ship natively in 4-bit (Kimi K3 is listed as `mxfp4` even from Moonshot), and hosts such as Fireworks and Together report their precision as unknown, so a filter like `["fp8", "bf16"]` would drop good hosts. Use `quantizations` only to exclude a host running a model below its release precision. As a backstop for every request whatever the harness, turn on zero data retention in OpenRouter's privacy settings and ignore the China-based hosts there.
- A model served only by its lab (for example Qwen Max) is closed weights in practice and is not used.
- ZDR does not cover OpenRouter's own web search plugin.
- Locally (Ollama, llama.cpp) is private by construction and free per token, but slow and smaller on ordinary hardware; fine for the `cheap` role once it passes the eval.

### 7. Cheap, unattended, long tasks

When quality matters, time does not, and cost does, in this order:

1. Prompt caching with a stable prefix (tools, system prompt, `AGENTS.md` first; volatile content last). In an agent loop most input tokens are re-reads, so this is the largest saving and it is free.
2. Newest mid-tier model at high effort before an older top-tier model. Measure cost per completed task, not per token: a cheaper model that needs more turns or retries is not cheaper.
3. Verification as the grader: tests, type checks, or a deterministic acceptance script decide success, and the harness retries on failure. Escalate to `frontier` only on a case that `default` failed twice. Caches are model-scoped, so a cascade forfeits cache reuse across its models.
4. Off-peak and batch pricing for parallel work: Anthropic Message Batches and OpenAI Batch run at half price, and OpenRouter lists `:batch` variants for some open-weight models; OpenAI Flex is a slower synchronous tier at a discount that fits an agent loop directly. Batch fits "run N tasks overnight", not a single long interactive loop, unless the harness can wait on each step.
5. Open-weight models (DeepSeek, Qwen, Kimi, GLM, Llama) through OpenRouter with the host allowlist and ZDR (section 6) as the `cheap` role, once they pass the eval on our tasks.
6. Task budgets and a max-turn cap on every unattended run so a stuck loop cannot spend unbounded money.

### High-level C4(context/container/component/code) diagram

```
person / CI ──> harness (pi) ──> pi-ai ──> OpenRouter (default: Claude, GPT, Gemini; ZDR)
                   │                  │          └──> allowlisted US/EU hosts for open-weight models
                   │                  └──> vendor APIs direct, when a native feature needs it
                   ├── reads AGENTS.md, specs/, docs/decisions/, .pi/settings.json, harness/models.json
                   ├── web search extension ──> search API (Exa / Parallel)
                   └── writes sessions (JSONL) ──> evals/cases ──> evals/run ──> evals/results
```

### Choices and Tradeoffs/Risks

- pi over OpenCode: less surface, easier to inspect and script, cheaper per task; weaker IDE and UI story. Mitigation: prompts are harness-neutral, so switching costs a config file.
- OpenRouter over direct APIs by default: one key, one bill, every model, account-wide privacy settings; costs a 5.5% fee, a hop, and native features can lag. Mitigation: BYOK for heavy models, go direct for features the gateway lacks, Vercel AI Gateway as a no-markup fallback.
- No Bedrock: one fewer account and bill; loses AWS-native IAM and billing. Mitigation: add it back as a provider if AWS becomes a requirement; pi supports it.
- Host allowlist over blocklist for open-weight models: safe as new hosts appear; can miss the cheapest host. Mitigation: review the allowlist in the monthly model sweep.
- Evals cost money and time on every switch. Mitigation: small case set, batch or slow tiers for the sweep, cheap judge model.
- No LLM observability platform (LangSmith, Langfuse) for now: pi's JSONL sessions are the traces, `evals/cases/` the datasets, `evals/results/` in git the history, and [SPEC-0004](../../specs/SPEC-0004-eval-benchmark-pages.md)'s static pages the dashboards. A platform would add a service to run, send prompts to a third party unless self-hosted (undoing zero data retention), and hold data outside the repo, so pages could no longer be rebuilt from committed files. LangSmith is also closed and tied to one vendor, with self-hosting limited to enterprise plans. Revisit when something here serves real users in production (live tracing, cost alerts, user feedback), when several people review and label results together, or when results in git grow too large to search (thousands of runs). If so, prefer self-hosted Langfuse (open source); keep the runner's per-call records exportable as OpenTelemetry traces, which Langfuse accepts, so adding it later needs no runner rewrite.
- Risk: eval gold answers drift stale or leak into prompts. Mitigation: the health checklist in this record and a reference-plus-null run before each sweep.

### Dependencies

Node.js 22.19+ for pi, from the pinned devenv environment ([Reproducible Environment](2026-09-26-reproducible-environment.md)). An OpenRouter key, plus vendor keys only where we go direct. A search API key for the web search extension. A sandbox (container) for eval runs, built with `devenv container build`.

### Interfaces

- `harness/models.json`: role to model mapping.
- `.pi/settings.json`: pi's default model (the `default` role) and package list (web search).
- `evals/cases/*.md|json`, `evals/run`, `evals/results/*.jsonl`.
- pi JSON or RPC mode as the boundary between harness and eval runner; one adapter per other harness, plus `direct` for single model calls.

## Key Results and retrospective feedback

To be filled after the first eval sweep: default model chosen, cost per completed task, and pass rate per model.
