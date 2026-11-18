# Decision Record 2026-11-12: Model Gateway

## Status timeline

2026-11-12: Proposed by Claude, at JC's request

2026-11-18: Amended by Claude, at JC's request, after GPT-6.2 Sol and Astra came out on 2026-11-17: `frontier` moves to GPT-6.2 Astra (JC's choice) and `judge` to GPT-6.2 Sol, and every comparison is now tested for significance, not read from the raw difference.

2026-11-15: Amended by Claude, at JC's request, after the first live runs on Vercel: the roles move to the models on the cost-per-task frontier (`default` GPT-6.1 Terra, `cheap` GPT-6 Luna, `judge` GPT-6.1 Sol), Kimi K3.1 Pro replaces Kimi K3 on the open-weight list, and pi's billed cost is confirmed; see Key Results.

2026-11-12: Amended by Claude, while implementing [SPEC-2026-11-12-model-gateway](../../specs/SPEC-2026-11-12-model-gateway.md): pi sends Vercel no gateway options at all, so a pi extension in the repo sends zero data retention and the host allowlist on each request; Claude Code sends them as an extra request body.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Every role reaches its model through one gateway, chosen by one setting, at the lowest cost per passed task that keeps zero data retention and the open-weight host allowlist.
Going back to OpenRouter, or trying another gateway, is a one-line change plus a key.

#### Non-functional

Private by default on whichever gateway is active.
Costs compared per passed task, not per token.

### Nice to haves

#### Functional

One key and one bill.
Claude plan API credit used where it can be.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A gateway or model router of our own.
Two gateways in everyday use at once.

#### Non-functional

A self-hosted gateway (LiteLLM, Portkey, Bifrost) while a hosted one meets the privacy rules.

## Decision

Vercel AI Gateway is the default route for every role.
It replaces OpenRouter as decided in section 2 of [Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md), and the OpenRouter-specific parts of its sections 6 and 8 become one gateway's settings.
OpenRouter stays configured and tested as the alternative, one setting away.
[SPEC-2026-11-12-model-gateway](../../specs/SPEC-2026-11-12-model-gateway.md) carries it out.

### Why Vercel, measured per task

Checked on 2026-11-12:

- Every frontier model, and every model that does best per passed task, is on both gateways at the same list prices, cache reads included: Claude Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5, GPT-6.1 Sol, GPT-6 Luna, and Gemini 4 Carbon ([Vercel models](https://ai-gateway.vercel.sh/v1/models), [OpenRouter models](https://openrouter.ai/api/v1/models)).
- Vercel adds no fee to provider prices ([pricing](https://vercel.com/docs/ai-gateway/pricing)), while OpenRouter charges 5.5% on credit purchases.
  Team-wide zero data retention on Vercel costs $0.10 per 1,000 requests ([ZDR](https://vercel.com/docs/ai-gateway/security-and-compliance/zdr)), about $0.0015 for a 15-turn task.
  So Vercel is about 5% cheaper per task on closed models, which are all four roles.
- In an agent loop most of the cost is context re-read from the prompt cache.
  On Cognition's FrontierCode 2.0, output is about a third of Opus 5.5's cost per run and under a fifth for GPT-6 Sol, Kimi K3, and GLM 5.3 ([leaderboard data](https://cognition.com/data/frontier-code-2.0/data.json), list output prices).
  The comparison below therefore prices each host's cache reads, not only its input and output.
- Open-weight models cost more on Vercel under our rules, because Vercel doesn't count DeepInfra as zero-retention while OpenRouter does.
  For a sample 15-turn task (10,000-token prefix, 3,000 new tokens and 1,000 output tokens a turn, so 89% of input is cache reads), the cheapest allowlisted zero-retention host costs:

  | Model | OpenRouter, with its 5.5% fee | Vercel, before its $0.0015 zero-retention charge |
  |-------|-------------------------------|---------------------------------------------------|
  | Claude Sonnet 5 | $0.383 | $0.363 |
  | Claude Opus 5.5 | $0.678 | $0.643 |
  | GPT-6 Sol | $0.383 | $0.363 |
  | Gemini 3.8 Flash | $0.133 | $0.126 |
  | DeepSeek V4.1 Flash | $0.016 | $0.036 |
  | GLM 5.3 | $0.125 | $0.197 |
  | Kimi K3 | $0.506 | $0.505 |
  | Qwen3.8 27B | $0.047 | $0.066 |

  Open-weight models run only in experiments today, so on the four roles Vercel is about 5% cheaper; with all eight models run equally, OpenRouter would be about 2% cheaper.
- Catalog: Vercel lists 323 language models (507 counting image, video, speech, and embedding models) and OpenRouter 447 text models.
  The gap is older and niche models, not ones we would pick.
- Both keep a session on one host so the prompt cache holds: OpenRouter's sticky routing ([caching](https://openrouter.ai/docs/guides/features/prompt-caching)) and Vercel's session affinity, on by default ([routing](https://vercel.com/docs/ai-gateway/models-and-providers/provider-options)).
  pi (1.0.1 when this was decided, 1.5.2 since 2026-11-13) adds cache markers on both and lists all eight of our models in its Vercel catalog.

### The gateway is one setting

`harness/models.json` gains a `gateway` key and a `gateways` table; roles use gateway-neutral IDs (Vercel's names), and each gateway maps the IDs it names differently.
Nothing outside the table names a gateway, so `harness/config.mjs`, `harness/sync`, `evals/lib/adapters.mjs`, `evals/run`, and `experiments/run` read the active entry instead of hard-coding OpenRouter.
A `<route>:<model>` ID overrides the route for one call, where the route is a gateway (`vercel`, `openrouter`) or a vendor's pi provider for direct access (`anthropic:claude-sonnet-5`).

### Privacy on Vercel

- pi's built-in Vercel provider sends every model through Vercel's Anthropic Messages endpoint, and pi sends `vercelGatewayRouting` only on its OpenAI-compatible path (checked in the pinned 1.0.1 and in 1.5.2), so on Vercel pi sends no gateway options at all.
  [`harness/gateway-options.ts`](../../harness/gateway-options.ts), a pi extension on pi's `before_provider_request` hook, adds `providerOptions.gateway` to each request: `zeroDataRetention: true`, and `only` for open-weight models.
  If it can't work out the options, it names a model no gateway serves, so the request fails instead of going out without them.
  `.pi/settings.json` loads it in this repo and the eval runner passes it to pi; `evals/test/run` checks the fields reach the request.
- Per-request zero data retention costs nothing extra; the team-wide setting ($0.10 per 1,000 requests) stays on as the backstop for pi outside the repo and other tools ([ZDR](https://vercel.com/docs/ai-gateway/security-and-compliance/zdr)).
  Disallow prompt training is a separate team-wide toggle, free, and turned on too.
- Alibaba Cloud and Moonshot AI are zero-retention providers on Vercel, so zero data retention alone doesn't keep open-weight models off China-based hosts; the `only` allowlist does.
- Claude Code can't send gateway options itself, but it merges `CLAUDE_CODE_EXTRA_BODY` into every request body, which Vercel documents for passing `providerOptions` ([Anthropic Messages API](https://vercel.com/docs/ai-gateway/sdks-and-apis/anthropic-messages-api)), so the eval runner sets it.
  It also sets `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`, since zero-retention Claude can be served from Bedrock or Vertex, which reject Anthropic's beta headers.
- Zero data retention needs a paid account: Pro or Enterprise, or purchased AI Gateway credits (free credits don't count).
- Open-weight models get the host allowlist per request through `providerOptions.gateway.only`, from the extension above.
  `only` is a hard filter: if no listed host can serve the model, the request fails instead of falling back.
- Claude Fable 5.x isn't available under zero data retention on any provider: Anthropic requires 30-day retention for those models ([Vercel ZDR](https://vercel.com/docs/ai-gateway/security-and-compliance/zdr), [Anthropic retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)).
- Zero data retention doesn't cover provider-side tools such as a provider's own web search; our web search runs through pi-web-access, outside the gateway.
- With zero data retention on, Vercel skips our own provider keys unless they are marked zero-retention, which needs our own agreement with that provider.
  So Claude plan API credit, which Vercel can use through the linked Console organization's Anthropic key ([Claude Code on AI Gateway](https://vercel.com/docs/ai-gateway/coding-agents/claude-code)), goes unused while team-wide zero data retention is on.

### Cost per task

- Results record the route and the cost the gateway billed; pi's own figure is a fallback, since pi prices each model at one list price and its pinned version undercounts long prompts on models with prompt-length pricing tiers (fixed in pi 1.1.0).
  The billed cost comes from each gateway's generation lookup (`GET /v1/generation?id=`), by the response's ID.
  Vercel documents chat completion IDs as generation IDs, but not Anthropic Messages IDs, which is what pi's Vercel provider gets back; live runs on 2026-11-15 showed pi's Vercel responses carry generation IDs, and the billed cost matched the change in the credit balance exactly.
  A run whose IDs aren't generation IDs still records pi's figure, marked as such.
  Claude Code reports no request IDs, so its cost is its own estimate: within 0.4% of the balance change for Sonnet 5, but 25 to 50 times too high for models it doesn't know, which it prices at Claude rates.
- `experiments/run --estimate` counts cache reads and writes.
- Effort is set per role and recorded, because it moves cost per task more than the gateway: on FrontierCode 2.0, Opus 5.5 costs $1.70 a run at medium effort and $12.82 at max.
- Newer models at the same list price are cheaper per task when cache reads cost less: Sonnet 5.5 and GPT-6.1 Sol list at $2 and $10 per million input and output tokens, like Sonnet 5 and GPT-6 Sol, with cache reads at $0.10 instead of $0.20.
  The eval decides whether they take the `default` and `judge` roles.

### Going back to OpenRouter

1. Set `gateway` to `openrouter` in `harness/models.json` and export `OPENROUTER_API_KEY`.
2. Run `harness/sync`, and `harness/sync --agent-dir ~/.pi/agent` for your own pi.
3. Turn on zero data retention and ignore the China-based hosts in OpenRouter's privacy settings, as in section 6 of [Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md).
4. Run the evals on the new route before relying on it.

OpenRouter's own-key terms changed since that record: own provider keys are free up to $25,000 of list-price usage a month, then 5% ([BYOK](https://openrouter.ai/docs/guides/overview/auth/byok)).

### High-level C4(context/container/component/code) diagram

```
person / CI ──> harness (pi + harness/gateway-options.ts) ──> active gateway (harness/models.json "gateway")
                    │                            ├── vercel (default): Claude, GPT, Gemini; ZDR per request and team-wide
                    │                            │      └──> allowlisted US/EU hosts for open-weight models
                    │                            └── openrouter (alternative): same roles; zdr per request
                    └──> vendor API direct, with a <vendor>:<model> ID
```

### Choices and Tradeoffs/Risks

- Vercel over OpenRouter: about 5% cheaper per task on closed models and no fee.
  Costs more for open-weight models under zero data retention, lists fewer text models, and zero data retention is a paid team setting.
  pi sends every Vercel model through Vercel's Anthropic Messages endpoint, so GPT, Gemini, and open-weight models pass through a translation layer; pi's changelog shows Vercel-specific fixes in the past (unsigned thinking replayed as text, fixed in 0.86.0; one-hour cache writes priced at the five-minute rate, fixed in 0.99.0).
  On that endpoint pi sends no gateway options, so privacy on Vercel depends on our extension as well as the team-wide settings.
  Mitigation: evals run per route, the offline test checks the options reach each request, and the swap back is one setting, tested without a key.
- Not Anthropic direct for the Claude roles: without plan credit it costs the same as Vercel, and it gives up zero data retention (Anthropic deletes API data within 30 days by default; zero data retention is arranged per organization through sales).
  Its first-party-only features (Message Batches, Files API, code execution) are unused today.
  Revisit if plan credit or those features come to matter more than zero data retention for Claude.
- Not a self-hosted gateway: it sells no model access, so it still needs a key and bill per vendor, and LiteLLM's releases were compromised twice in 2026 (PyPI in March; PyPI and Docker images on October 21).
- Neither gateway is open source; pi (MIT) is the layer that keeps them swappable.

### Dependencies

A Vercel team with purchased AI Gateway credits (or a Pro plan), and `AI_GATEWAY_API_KEY`.
`OPENROUTER_API_KEY` only when switching back.

### Interfaces

`harness/models.json`, sketched:

```json
{
  "gateway": "vercel",
  "roles": {
    "default": "openai/gpt-6.1-terra",
    "cheap": "openai/gpt-6-luna",
    "frontier": "anthropic/claude-opus-5.5",
    "judge": "openai/gpt-6.1-sol"
  },
  "effort": { "default": "medium" },
  "openWeightModels": ["deepseek/deepseek-v4.1-flash", "zai/glm-5.3", "moonshotai/kimi-k3.1-pro", "alibaba/qwen3.8-27b"],
  "gateways": {
    "vercel": {
      "piProvider": "vercel-ai-gateway",
      "keyEnv": "AI_GATEWAY_API_KEY",
      "openaiBaseUrl": "https://ai-gateway.vercel.sh/v1",
      "claudeCodeBaseUrl": "https://ai-gateway.vercel.sh/claude-code",
      "claudeCodeEnv": { "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1" },
      "modelsUrl": "https://ai-gateway.vercel.sh/v1/models",
      "routing": { "zeroDataRetention": true },
      "openWeightHosts": ["fireworks", "togetherai", "parasail", "baseten", "modal", "deepinfra"]
    },
    "openrouter": {
      "piProvider": "openrouter",
      "keyEnv": "OPENROUTER_API_KEY",
      "openaiBaseUrl": "https://openrouter.ai/api/v1",
      "claudeCodeBaseUrl": "https://openrouter.ai/api",
      "modelsUrl": "https://openrouter.ai/api/v1/models",
      "routing": { "zdr": true, "data_collection": "deny" },
      "openWeightHosts": ["deepinfra", "fireworks", "together", "parasail", "baseten", "coreweave", "modal"],
      "modelIds": { "zai/glm-5.3": "z-ai/glm-5.3", "alibaba/qwen3.8-27b": "qwen/qwen3.8-27b" }
    }
  }
}
```

Results lines gain `route`, `effort`, `cost_source` (`gateway`, or the harness or API whose estimate it is), and `served_hosts`.

## Key Results and retrospective feedback

First eval sweep on Vercel, 2026-11-15, with GPT-6.2 Sol and Astra added on 2026-11-18: the 13 cases in `evals/cases/` through pi 1.5.2, with zero data retention on every request, results in `evals/results/2026-11-15-*.jsonl` and `2026-11-18-*.jsonl`.
Every pi run used medium effort (the `default` role sets it, and it is pi's default for the rest).
The recorded cost of the sweep and the checks was $13.38, plus $2.29 for the GPT-6.2 runs; OpenRouter wasn't run, so there is no measured gap to it yet.

### Live checks ([spec](../../specs/SPEC-2026-11-12-model-gateway.md) items 3 to 5)

| Run | Case | Served by | Recorded cost | Vercel's figure | `experiments/run --estimate` |
|---|---|---|---|---|---|
| pi, `default` (then Sonnet 5) | fix-broken-link | anthropic | $0.0221 | $0.0221 | $0.1309 |
| Claude Code, Sonnet 5 | fix-broken-link | anthropic | $0.1596 (its own estimate) | $0.1603 | $0.1309 |
| direct, DeepSeek V4.1 Flash | read-csv-total | modal (allowlisted) | $0.0002 | $0.0002 | $0.0005 |
| pi, DeepSeek V4.1 Flash | fix-broken-link | modal (allowlisted) | $0.0040 | $0.0040 | $0.0142 |

Vercel's figure is the change in the credit balance (`GET /v1/credits`) across each run, which matched pi's and direct mode's billed cost exactly.
The response metadata reported `enabledZeroDataRetention: true`, and Kimi K3.1 Pro was served only by baseten and parasail, both on the allowlist.

Over the whole sweep the estimate is about 3 times the measured cost for Opus, Sonnet, and the GPT Sol and Terra models (it assumes 8 turns; they took about 4), 1.5 to 2 times for Haiku 5.5 and GPT-6 Luna, and 2 to 3 times too low for Gemini 3.8 Flash and Gemini 4 Carbon, which took 10 to 17 turns.
So it bounds a budget for most models but not for a model that loops.

### Pass rate and cost per passed task

| Model | Pass rate (range across reps) | Runs | Cost per passed task | Turns | Time (s) |
|---|---|---|---|---|---|
| GPT-6.1 Terra | 100% (100%) | 38, plus 1 timeout | $0.0155 | 3.9 | 30 |
| GPT-6.1 Sol | 100% (100%) | 39 | $0.0283 | 4.7 | 32 |
| GPT-6.2 Astra | 100% | 13 (1 rep) | $0.0886 | 3.5 | 28 |
| Gemini 4 Hydrogen | 100% | 13 (1 rep) | $0.0491 | 6.1 | 36 |
| Gemini 4 Carbon | 100% | 13 (1 rep) | $0.1835 | 9.8 | 168 |
| DeepSeek V4.1 Flash | 95% (92% to 100%) | 39 | $0.0087 | 6.2 | 31 |
| GPT-6.2 Sol | 95% (92% to 100%) | 39 | $0.0308 | 4.9 | 29 |
| Muse Ember | 92% (92%) | 39 | $0.0050 | 6.0 | 27 |
| Claude Opus 5.5 | 92% (92%) | 39 | $0.0672 | 4.1 | 33 |
| GPT-6 Sol | 92% (92%) | 39 | $0.0334 | 4.1 | 29 |
| Kimi K3.1 Pro | 92% | 13 (1 rep) | $0.0465 | 4.5 | 29 |
| GPT-6 Luna | 90% (85% to 92%) | 39 | $0.0029 | 4.5 | 35 |
| Claude Haiku 5.5 | 87% (85% to 92%) | 39 | $0.0038 | 4.7 | 33 |
| Claude Sonnet 5.5 | 85% (85%) | 39 | $0.0288 | 3.7 | 28 |
| Claude Sonnet 5 | 67% (62% to 69%) | 39 | $0.0434 | 3.9 | 30 |
| Gemini 3.8 Flash | 38% | 13 (1 rep) | $0.2938 | 16.6 | 88 |

On these cases the cost-per-task frontier runs GPT-6 Luna, Muse Ember, DeepSeek V4.1 Flash, GPT-6.1 Terra; every other model passes less for more.
`claim-next-spec` separates the models most, though not by enough for significance: Opus 5.5, Sonnet 5 and 5.5, GPT-6 Sol, Haiku 5.5, and Muse Ember failed it on every rep, and GPT-6.2 Sol on two of three.
GPT-6.1 Terra's timeout (add-make-target, 2 turns in 300 seconds) is kept out of the pass rate as the runner does for every timeout; counted as a failure it would be 97%.

### Significance

Each comparison is paired by case, since every model ran the same 13 cases.
A pass-rate difference is the mean over cases of the two models' per-case pass rates, tested with an exact two-sided sign-flip test over the cases; cost per passed task is compared as a ratio, with a 95% interval from resampling the cases 10,000 times.
A difference counts only at p < 0.05, or when the ratio's interval excludes 1.

| Comparison | Pass rate | p | Cost per passed task, ratio (95% interval) |
|---|---|---|---|
| GPT-6.1 Terra vs Claude Sonnet 5 | 100% vs 67% | 0.06 | 0.36 (0.21 to 0.55) |
| GPT-6.1 Terra vs Claude Sonnet 5.5 | 100% vs 85% | 0.50 | 0.54 (0.38 to 0.77) |
| GPT-6.1 Terra vs GPT-6.1 Sol | 100% vs 100% | 1 | 0.55 (0.52 to 0.59) |
| GPT-6.1 Terra vs GPT-6.2 Sol | 100% vs 95% | 1 | 0.51 (0.43 to 0.58) |
| GPT-6 Luna vs Gemini 3.8 Flash | 90% vs 38% | 0.008 | 0.01 (0.00 to 0.02) |
| GPT-6 Luna vs Muse Ember | 90% vs 92% | 1 | 0.59 (0.43 to 0.78) |
| GPT-6 Luna vs Claude Haiku 5.5 | 90% vs 87% | 1 | 0.78 (0.54 to 1.14) |
| GPT-6 Luna vs DeepSeek V4.1 Flash | 90% vs 95% | 1 | 0.34 (0.27 to 0.44) |
| GPT-6.2 Astra vs Claude Opus 5.5 | 100% vs 92% | 1 | 1.32 (0.95 to 1.92) |
| GPT-6.2 Astra vs Gemini 4 Carbon | 100% vs 100% | 1 | 0.48 (0.37 to 0.69) |
| GPT-6.2 Astra vs GPT-6.2 Sol | 100% vs 95% | 1 | 2.88 (2.47 to 3.29) |
| GPT-6.2 Sol vs GPT-6.1 Sol | 95% vs 100% | 1 | 1.09 (0.93 to 1.30) |
| GPT-6.1 Sol vs GPT-6 Sol | 100% vs 92% | 1 | 0.84 (0.67 to 0.97) |
| Claude Sonnet 5.5 vs Claude Sonnet 5 | 85% vs 67% | 0.38 | 0.66 (0.43 to 0.97) |

Only one pass-rate difference is significant: GPT-6 Luna over Gemini 3.8 Flash.
With 13 cases a sign-flip test can't reach p < 0.05 unless at least 6 cases go the same way, so this suite can only show very large pass-rate gaps; Terra against Sonnet 5, with 5 such cases, stops at 0.06.
Cost per passed task separates models far better: most of the ratios above exclude 1.

The pairs in spec item 8: Sonnet 5.5 and GPT-6.1 Sol pass about as often as the models they would replace (no significant difference) and cost significantly less per passed task, a third and 16% less, so either could take its role.

The outside benchmarks carry their own noise.
FrontierCode 2.0 has 132 tasks, so a score near 50% carries about ±8.5 points of sampling error, more than any gap among its top models.
Artificial Analysis puts its index's 95% confidence interval under ±1 point ([methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking)), so gaps of 2 or more points there are real.

### Outside benchmarks

Four models pass every case here, so the suite can't rank the most capable ones.
Two benchmarks that price whole agent tasks were checked on 2026-11-15: Cognition's FrontierCode 2.0 ([data](https://cognition.com/data/frontier-code-2.0/data.json)) and the Artificial Analysis Intelligence Index ([leaderboard](https://artificialanalysis.ai/leaderboards/models)).
Their cost-per-task frontiers, cheapest first, among models that Vercel serves with zero data retention and that solve at least a sixth of the tasks or score at least 30:

- FrontierCode 2.0 (share of tasks solved, cost per run at the effort shown): GPT-6 Luna (18% at $0.09, medium), Claude Haiku 5.5 (32% at $0.37, max), GPT-6.2 Sol (42% at $0.69, medium; 48% at $1.29, max), GPT-6.2 Astra (49% at $4.29, xhigh), Claude Opus 5.5 (49% at $5.18, xhigh; 52% at $12.82, max).
  GPT-6.2 Sol at max effort comes within a point of GPT-6.2 Astra and Opus 5.5 at xhigh for a quarter to a third of their cost, and the GPT-6.2 models push Gemini 4 Carbon off the frontier.
- Artificial Analysis (index, cost per task): Muse Ember (36 at $0.14), GPT-6.1 Terra (51 at $0.96), GPT-6.2 Sol (57 at $1.01), GPT-6.2 Astra (62 at $4.00); Gemini 4 Carbon scores 60 at $5.48 and Opus 5.5 59 at $10.04.

Claude Fable 5.2 tops both but isn't available with zero data retention.
Xiaomi MiMo V2.6 Flash (27 at $0.13) is on Artificial Analysis's frontier just below Muse Ember, but Vercel has no zero-retention host for it, so the privacy rules leave it out.

### Roles chosen

Our cases can't show the capability gap between tiers: even GPT-6 Luna's 90% isn't significantly below GPT-6.1 Terra's 100%.
So the role sets the tier (small models for `cheap`, mid-tier for `default` and `judge`, top tier for `frontier`), with the outside benchmarks as the evidence that the tiers differ.
Within a tier, `default` and `cheap` take the cheapest model per passed task on our cases whose pass rate isn't significantly worse.
`frontier` and `judge` exist for accuracy more than cost, so where our cases can't separate the candidates, they take the strongest on the outside benchmarks.

- `default`: GPT-6.1 Terra, instead of Sonnet 5.
  No model passes significantly more of our cases, and it costs significantly less per passed task than every other mid-tier model tested: about half GPT-6.1 and 6.2 Sol's, and a third of Sonnet 5's, Gemini 4 Hydrogen's, and Kimi K3.1 Pro's.
  GPT-6.2 Sol is significantly stronger on Artificial Analysis (57 against 51), so it is the step up if everyday work gets harder than these cases.
- `cheap`: GPT-6 Luna, instead of Gemini 3.8 Flash.
  It passes significantly more cases than Gemini 3.8 Flash for 1% of the cost per passed task.
  Against Muse Ember it passes as often for significantly less (0.59 times); Muse Ember is significantly stronger on Artificial Analysis (36 against 28) at the same cost there.
  Against Haiku 5.5 neither difference is significant, so either would do.
- `frontier`: GPT-6.2 Astra, instead of Opus 5.5.
  It is the most capable zero-retention model on Artificial Analysis, at 40% of Opus 5.5's cost per task, and matches Opus 5.5 at xhigh effort on FrontierCode 2.0 for 17% less; among zero-retention models only Opus 5.5 at max effort solves more there, at three times the cost.
  GPT-6.2 Sol at max effort is the cheaper alternative: within a point of both on FrontierCode 2.0, but 5 points behind Astra on Artificial Analysis.
  Here neither its pass rate nor its cost per passed task differs significantly from Opus 5.5's (one rep against three), and FrontierCode 2.0's gaps are within its noise, so the choice rests on Artificial Analysis, where Astra leads Opus 5.5 by 3 points, outside that index's ±1.
  Gemini 4 Carbon passed as often here at about twice Astra's cost per passed task, significantly more.
  The suite can't rank this role until it has cases the top models fail.
- `judge`: GPT-6.2 Sol, instead of GPT-6 Sol.
  It is the strongest mid-tier model on Artificial Analysis (57, against GPT-6.1 Sol's 55 when last listed on 2026-11-15 and GPT-6.1 Terra's 51), and against GPT-6.1 Sol, at the same price, neither its pass rate (95% against 100%) nor its cost per passed task differs significantly here.
  No case uses the judge yet; once one does, runs of OpenAI models should be graded by a judge from another vendor.
- Open-weight list: Kimi K3.1 Pro replaces Kimi K3; it is newer and lists at $2 and $10 per million input and output tokens instead of $3 and $15.

All four roles are now OpenAI models.
Vercel serves them from both OpenAI and Azure under zero data retention, so one host's outage doesn't stop them, but an OpenAI-wide problem would; Opus 5.5 and the open-weight models are the fallback.

Next: more cases, including ones the top models fail, so the suite can show smaller pass-rate gaps and rank the top tier (no spec covers this yet); significance in `evals/report` itself, so these comparisons don't need a one-off script; and the same sweep on OpenRouter to measure the gap.
