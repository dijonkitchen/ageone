# Harness

How agentic work in this repo reaches a model, as decided in [Vendor-Neutral AI Harness](../docs/decisions/2026-09-26-vendor-neutral-ai-harness.md) and [Model Gateway](../docs/decisions/2026-11-12-model-gateway.md).

## Files

- [`models.json`](models.json): the one place models and the gateway are chosen.
  - `gateway` picks the route for every role: `vercel` ([Vercel AI Gateway](https://vercel.com/docs/ai-gateway), the default) or `openrouter`.
  - `roles` maps `default`, `cheap`, `frontier`, and `judge` to gateway-neutral `creator/model` IDs (Vercel's names), and `effort` sets a role's reasoning effort, passed to pi as `--thinking`.
  - `openWeightModels` lists the models that may run only on the US and EU host allowlist.
  - `gateways` holds everything specific to each gateway: pi's provider name, the key's environment variable, its OpenAI-compatible and Claude Code URLs, its price list, its privacy settings, its names for the allowlisted hosts, and `modelIds` where it names a model differently.
  - `harnesses` pins each harness's version.
- [`gateway-options.ts`](gateway-options.ts): a pi extension that adds the gateway's privacy and host options to each request pi can't route itself.
  pi's built-in Vercel provider speaks the Anthropic Messages API and sends no Vercel options, so this is what sends zero data retention and the host allowlist on Vercel; OpenRouter's routing goes through pi's `models.json` instead.
- [`web-search.json`](web-search.json): settings for the [pi-web-access](https://github.com/nicobailon/pi-web-access) extension, pinned to Exa (keyed with `EXA_API_KEY`, keyless otherwise).
- [`../.pi/settings.json`](../.pi/settings.json): pi's project settings, holding the `default` role, its effort, the gateway extension, and the web search package; `harness/sync` writes the first three and keeps the other keys, so the package pin is edited by hand.
- `config.mjs`, `sync`, `pi`: the scripts below. `config.mjs` is the only code that knows how a gateway takes its options.

## Use

```sh
export AI_GATEWAY_API_KEY=...          # the key for the active gateway (OPENROUTER_API_KEY on OpenRouter)
harness/pi                             # the pinned pi, on the default role through the active gateway
harness/pi --provider vercel-ai-gateway --model deepseek/deepseek-v4.1-flash -p "..."   # any other model on Vercel
harness/sync --agent-dir ~/.pi/agent   # once: OpenRouter routing and web search settings for your own pi
```

pi asks to trust the project the first time, because `.pi/settings.json` loads the gateway extension and installs the web search extension.
Outside this repo your pi doesn't load the extension, so Vercel applies only the team-wide settings below.

The eval and experiment runners take a model as a role, a `creator/model` ID on the active gateway, or a `<route>:<model>` ID, where the route is a gateway (`openrouter:deepseek/deepseek-v4.1-flash`) or a vendor's own API (`anthropic:claude-sonnet-5`, with `ANTHROPIC_API_KEY`).
`--gateway openrouter` on `evals/run` and `experiments/run` sends roles and plain IDs through another gateway for one run.

## Change a model

1. Edit the role in `models.json`, using a gateway-neutral ID from Vercel's [model list](https://vercel.com/ai-gateway/models).
   If OpenRouter names it differently, add the pair to `gateways.openrouter.modelIds`.
2. Run `harness/sync`, which mirrors `default` into `.pi/settings.json`; CI fails when they disagree.
3. Run the evals on the new model before relying on it ([evals](../evals/README.md)).

An open-weight model gets the host allowlist only when its ID is in `openWeightModels`.
The allowlist is a hard filter on both gateways: if no listed host can serve the model, the request fails instead of falling back.

## Switch gateway

To go back to OpenRouter, or to try a gateway again after a change:

1. Set `gateway` to `openrouter` in `models.json` and export `OPENROUTER_API_KEY`.
2. Run `harness/sync`, and `harness/sync --agent-dir ~/.pi/agent` for your own pi.
3. Set the gateway's account settings below.
4. Run the evals on the new route before relying on it; `evals/report` keeps each route's results apart.

Nothing else changes: `evals/test/run` checks both gateways' settings, requests, and Claude Code environment on every pull request, without a key.

## Account settings to set by hand

Vercel:

- Buy AI Gateway credits (or use a Pro or Enterprise plan).
  Zero data retention needs a paid account, and free credits don't count, so requests fail with a `403` until then.
- In the AI Gateway settings, turn on **Zero Data Retention** and **Disallow Prompt Training** for the team.
  The harness already asks for zero data retention on each request, which is free; the team-wide setting ($0.10 per 1,000 requests) is the backstop for pi outside this repo and other tools.
  Team-wide disallow prompt training is free.
- Don't mark any own provider key (BYOK) as zero-retention unless that provider's agreement covers it; with zero data retention on, Vercel skips unmarked keys.

OpenRouter:

- `models.json` sends zero data retention and `data_collection: "deny"` on every request, and pins open-weight models to the allowlist.
  As a backstop for tools that bypass it, also turn on zero data retention in OpenRouter's privacy settings and add the China-based hosts (such as DeepSeek, Moonshot, Z.AI, MiniMax, Alibaba, Baidu, SiliconFlow, and StreamLake) to its ignored providers.
