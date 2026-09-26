# Decision Record 2026-09-26: Vendor-Neutral AI Harness

## Status timeline

2026-09-26: Proposed by Claude, at JC's request

2026-09-26: Amended by Claude, at JC's request: checked against pi's current docs. Fixed the repo link and where pi reads model config, added web search and open-weight data privacy.

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

### 2. Model access: direct first, gateway when needed, Bedrock for AWS

- Default to each vendor's native API through `pi-ai`. Fewest hops, and native features (prompt caching, adaptive thinking, effort, 1M context, batch) arrive first there.
- Add a gateway only for a reason: one bill and spend attribution, fallbacks, or data that cannot leave your infrastructure. Self-hosted: LiteLLM (MIT, OpenAI-compatible, 100+ providers). Managed: OpenRouter (largest catalog, 5.5% fee on credits, BYOK to remove it) or Vercel AI Gateway (best for TypeScript teams, built-in failover).
- AWS Bedrock is one provider among several, not the neutral layer. Use it when AWS IAM, billing, private networking, or compliance matter, and for open-weight models (Llama, DeepSeek, Mistral, Qwen) and Amazon Nova next to Claude. Its Converse API is model-agnostic across Bedrock models and its batch inference accepts Converse format at a discount. Known costs: OpenAI and Google models are not on it, Claude features and pricing lag the first-party API, and model IDs are prefixed (`anthropic.…`). Anthropic also offers Claude Platform on AWS, Anthropic-operated with same-day API parity, SigV4 auth, and AWS Marketplace billing, which is the better choice when the reason for AWS is billing and IAM rather than the Bedrock catalog.

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
- Runner: `evals/run` drives pi in JSON or RPC mode with a fresh sandbox per case. Start with a script; adopt Inspect AI or promptfoo once cases outgrow it. Both compare providers side by side and record cost and latency.
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
- Run those models on hosts that do not train on or retain prompts: AWS Bedrock (runs the weights inside AWS, no sharing with model providers), US or EU inference providers (Groq, Cerebras, Fireworks, Together), or OpenRouter.
- OpenRouter, the easiest single key: in account privacy settings turn on zero data retention and add the labs' first-party endpoints to ignored providers. That applies to every request whatever the harness. pi can also send the same `provider` routing fields per model (`openRouterRouting`: `zdr`, `data_collection: "deny"`, `only`, `ignore`). Note ZDR does not cover OpenRouter's own web search plugin.
- Locally (Ollama, llama.cpp) is private by construction and free per token, but slow and smaller on ordinary hardware; fine for the `cheap` role once it passes the eval.

### 7. Cheap, unattended, long tasks

When quality matters, time does not, and cost does, in this order:

1. Prompt caching with a stable prefix (tools, system prompt, `AGENTS.md` first; volatile content last). In an agent loop most input tokens are re-reads, so this is the largest saving and it is free.
2. Newest mid-tier model at high effort before an older top-tier model. Measure cost per completed task, not per token: a cheaper model that needs more turns or retries is not cheaper.
3. Verification as the grader: tests, type checks, or a deterministic acceptance script decide success, and the harness retries on failure. Escalate to `frontier` only on a case that `default` failed twice. Caches are model-scoped, so a cascade forfeits cache reuse across its models.
4. Off-peak and batch pricing for parallel work: Anthropic Message Batches and Bedrock batch inference (Converse format) run at half price; OpenAI Flex is a slower synchronous tier at a discount that fits an agent loop directly. Batch fits "run N tasks overnight", not a single long interactive loop, unless the harness can wait on each step.
5. Open-weight models (DeepSeek, Qwen, Kimi, Llama) through Bedrock, Groq, or OpenRouter with ZDR (section 6) as the `cheap` role, once they pass the eval on our tasks.
6. Task budgets and a max-turn cap on every unattended run so a stuck loop cannot spend unbounded money.

### High-level C4(context/container/component/code) diagram

```
person / CI ──> harness (pi) ──> pi-ai ──> vendor APIs (Anthropic, OpenAI, Google, ...)
                   │                  └──> AWS Bedrock (Claude + open-weight)
                   │                  └──> gateway (LiteLLM / OpenRouter), only if needed
                   ├── reads AGENTS.md, specs/, docs/decisions/, .pi/settings.json, harness/models.json
                   ├── web search extension ──> search API (Exa / Parallel)
                   └── writes sessions (JSONL) ──> evals/cases ──> evals/run ──> evals/results
```

### Choices and Tradeoffs/Risks

- pi over OpenCode: less surface, easier to inspect and script, cheaper per task; weaker IDE and UI story. Mitigation: prompts are harness-neutral, so switching costs a config file.
- Direct APIs over a gateway by default: native features and lowest cost; no single bill. Mitigation: add LiteLLM when spend reporting or fallbacks matter.
- Bedrock as one provider, not the hub: avoids the missing-vendor and feature-lag problem; costs some AWS-native convenience. Mitigation: Claude Platform on AWS for Claude, Bedrock for open-weight.
- Evals cost money and time on every switch. Mitigation: small case set, batch or slow tiers for the sweep, cheap judge model.
- Risk: eval gold answers drift stale or leak into prompts. Mitigation: the health checklist in this record and a reference-plus-null run before each sweep.

### Dependencies

Node.js 22.19+ for pi. Provider credentials per vendor, AWS credentials for Bedrock. A search API key for the web search extension. A sandbox (container) for eval runs.

### Interfaces

- `harness/models.json`: role to model mapping.
- `.pi/settings.json`: pi's default model (the `default` role) and package list (web search).
- `evals/cases/*.md|json`, `evals/run`, `evals/results/*.jsonl`.
- pi JSON or RPC mode as the boundary between harness and eval runner.

## Key Results and retrospective feedback

To be filled after the first eval sweep: default model chosen, cost per completed task, and pass rate per model.
