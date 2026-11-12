# Decision Record 2026-11-12: Model Gateway

## Status timeline

2026-11-12: Proposed by Claude, at JC's request

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
  The pinned pi (1.0.1) adds cache markers on both and lists all eight of our models in its Vercel catalog.

### The gateway is one setting

`harness/models.json` gains a `gateway` key and a `gateways` table; roles use gateway-neutral IDs (Vercel's names), and each gateway maps the IDs it names differently.
Nothing outside the table names a gateway, so `harness/config.mjs`, `harness/sync`, `evals/lib/adapters.mjs`, `evals/run`, and `experiments/run` read the active entry instead of hard-coding OpenRouter.
A `<route>:<model>` ID overrides the route for one call, where the route is a gateway (`vercel`, `openrouter`) or a vendor's pi provider for direct access (`anthropic:claude-sonnet-5`).

### Privacy on Vercel

- pi sends Vercel only `only` and `order` from `vercelGatewayRouting`, not `zeroDataRetention`, so zero data retention is the team-wide setting.
  Disallow prompt training is a separate team-wide toggle, free, and turned on too.
- Zero data retention needs a paid account: Pro or Enterprise, or purchased AI Gateway credits (free credits don't count).
- Open-weight models get the host allowlist per request through `vercelGatewayRouting.only`.
  `only` is a hard filter: if no listed host can serve the model, the request fails instead of falling back.
- Claude Fable 5.x isn't available under zero data retention on any provider: Anthropic requires 30-day retention for those models ([Vercel ZDR](https://vercel.com/docs/ai-gateway/security-and-compliance/zdr), [Anthropic retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)).
- Zero data retention doesn't cover provider-side tools such as a provider's own web search; our web search runs through pi-web-access, outside the gateway.
- With zero data retention on, Vercel skips our own provider keys unless they are marked zero-retention, which needs our own agreement with that provider.
  So Claude plan API credit, which Vercel can use through the linked Console organization's Anthropic key ([Claude Code on AI Gateway](https://vercel.com/docs/ai-gateway/coding-agents/claude-code)), goes unused while team-wide zero data retention is on.

### Cost per task

- Results record the route and the cost the gateway billed; pi's own figure is a fallback, since pi prices each model at one list price and its pinned version undercounts long prompts on models with prompt-length pricing tiers (fixed in pi 1.1.0).
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
person / CI ──> harness (pi) ──> pi-ai ──> active gateway (harness/models.json "gateway")
                                    │          ├── vercel (default): Claude, GPT, Gemini; team-wide ZDR
                                    │          │      └──> allowlisted US/EU hosts for open-weight models
                                    │          └── openrouter (alternative): same roles; zdr per request
                                    └──> vendor API direct, with a <vendor>:<model> ID
```

### Choices and Tradeoffs/Risks

- Vercel over OpenRouter: about 5% cheaper per task on closed models and no fee.
  Costs more for open-weight models under zero data retention, lists fewer text models, and zero data retention is a paid team setting.
  pi sends every Vercel model through Vercel's Anthropic Messages endpoint, so GPT, Gemini, and open-weight models pass through a translation layer; pi's changelog shows Vercel-specific fixes in the past (unsigned thinking replayed as text, fixed in 0.86.0; one-hour cache writes priced at the five-minute rate, fixed in 0.99.0).
  Mitigation: evals run per route, and the swap back is one setting, tested without a key.
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
    "default": "anthropic/claude-sonnet-5",
    "cheap": "google/gemini-3.8-flash",
    "frontier": "anthropic/claude-opus-5.5",
    "judge": "openai/gpt-6-sol"
  },
  "effort": { "default": "medium" },
  "openWeightModels": ["deepseek/deepseek-v4.1-flash", "zai/glm-5.3", "moonshotai/kimi-k3", "alibaba/qwen3.8-27b"],
  "gateways": {
    "vercel": {
      "piProvider": "vercel-ai-gateway",
      "keyEnv": "AI_GATEWAY_API_KEY",
      "openaiBaseUrl": "https://ai-gateway.vercel.sh/v1",
      "claudeCodeBaseUrl": "https://ai-gateway.vercel.sh/claude-code",
      "modelsUrl": "https://ai-gateway.vercel.sh/v1/models",
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

Results lines gain `route` and `cost_source` (`gateway` or `pi`).

## Key Results and retrospective feedback

To be filled after the first eval sweep on Vercel: cost per passed task and pass rate per role, and the measured gap to OpenRouter if both are run.
