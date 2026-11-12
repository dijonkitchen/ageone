# SPEC-2026-11-12-model-gateway: Vercel AI Gateway by Default, One Setting From OpenRouter

Moves every model role from OpenRouter to [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) and makes the gateway one setting in [`harness/models.json`](../harness/models.json), so going back to OpenRouter is a one-line change plus its key.
The reasons and the numbers behind them are in [Model Gateway](../docs/decisions/2026-11-12-model-gateway.md).

It also makes cost per passed task, not price per token, what the harness records and estimates.
In an agent loop most of the cost is context re-read from the prompt cache, so effort level, cache-read prices, and pass rate move the bill more than the gateway does.

## Functional requirements

- One `gateway` key in `harness/models.json` picks the route for every role: `vercel` (the default) or `openrouter`.
  Roles name models by gateway-neutral IDs, such as `anthropic/claude-sonnet-5`.
  Where a gateway names a model differently, its entry maps the ID: OpenRouter calls `zai/glm-5.3` `z-ai/glm-5.3`, and `alibaba/qwen3.8-27b` `qwen/qwen3.8-27b`.
- Each gateway's entry holds everything specific to it, and no script names a gateway outside it: pi's provider name, the key's environment variable, the OpenAI-compatible and Claude Code base URLs, the price list URL, its privacy settings, and its host names for the open-weight allowlist.
- A single run can pick another route, so the two gateways can be compared on the same cases and a vendor's own API still works:
  `--gateway openrouter` on `evals/run` and `experiments/run`, and a `<route>:<model>` ID anywhere a model is accepted, such as `openrouter:deepseek/deepseek-v4.1-flash` or `anthropic:claude-sonnet-5` (direct, with `ANTHROPIC_API_KEY`).
- On Vercel:
  - pi uses its built-in `vercel-ai-gateway` provider with `AI_GATEWAY_API_KEY`.
  - Every request carries `providerOptions.gateway.zeroDataRetention: true`, and open-weight models are pinned to the US and EU host allowlist with `providerOptions.gateway.only`, using Vercel's host names (`fireworks`, `togetherai`, `parasail`, `baseten`, `modal`, `deepinfra`; CoreWeave isn't on Vercel).
    pi's Vercel provider sends no gateway options (it speaks the Anthropic Messages API, and pi sends `vercelGatewayRouting` only on its OpenAI-compatible path), so a pi extension in the repo adds them to each request; `direct` mode builds its own requests and sets them itself.
  - Zero data retention and no prompt training are also on as team-wide settings in Vercel, as the backstop for pi outside the repo and other tools.
  - Claude Code runs through Vercel's Claude Code endpoint, `https://ai-gateway.vercel.sh/claude-code`, and sends the same options as an extra request body.
- On OpenRouter, routing works as it does today: `zdr`, `data_collection: "deny"`, and `only` with no fallbacks for open-weight models.
- Each results line records the route it ran through and the cost the gateway billed.
  pi prices a call from its own catalog at one list price per model, while the gateway bills the host that served it plus any surcharge, so pi's figure is kept only as a fallback and marked as such.
- `experiments/run --estimate` prices from the active gateway's model list and counts cache reads and writes in agent cases, instead of charging every input token at the full rate.
- A role can set a reasoning effort in `harness/models.json`, passed to pi as `--thinking`, so effort is chosen per role and recorded with each result.

## Non-functional requirements

- Switching gateway is an edit to `harness/models.json`, the new key, and `harness/sync`, with no code change.
- Private by default on either gateway: zero data retention and no training for every model, and open-weight models only on allowlisted US and EU hosts.
  A request that can't meet that fails instead of falling back.
- Honest comparisons: `evals/report` groups results by route as well as model, and never pools two gateways' results unless asked.
- No new dependencies: each gateway's public model list is the price source.
- The OpenRouter path stays tested without a key, so it can't rot while unused.

## Definition of done

1. `harness/models.json` has `gateway` set to `vercel`, entries for `vercel` and `openrouter` under `gateways`, gateway-neutral role IDs, and an optional effort per role; `harness/sync` and CI's `harness/sync --check` work with either gateway.
2. `evals/test/run` (no keys, mock provider) covers both gateways: for each, the generated pi `models.json` and `.pi/settings.json`, the key `evals/run` requires, the URL and privacy fields of a `direct` request, and the Claude Code environment.
   Switching `gateway` changes nothing else, and the test passes in CI.
3. With `AI_GATEWAY_API_KEY`, recorded in the pull request: an agent case runs end to end in pi on the `default` role, one case runs in `claude-code`, one in `direct` mode, and one on an open-weight model served by an allowlisted host, with the served host shown in Vercel's logs or response.
4. Results lines carry the route and the billed cost; for the runs in item 3, the recorded cost matches Vercel's own figure for those requests.
5. `experiments/run --estimate` counts cache reads, and its estimate for the runs in item 3 is shown next to their measured cost in the pull request.
6. `harness/README.md`, `evals/README.md`, and the decision record describe the Vercel account settings to set by hand (purchased credits, team-wide zero data retention, disallow prompt training) and the steps to go back to OpenRouter.
7. The rows in `specs/PRIORITIES.md` blocked on an `OPENROUTER_API_KEY` wait on an `AI_GATEWAY_API_KEY` instead.
8. The eval compares `default` with `anthropic/claude-sonnet-5.5` and `judge` with `openai/gpt-6.1-sol` (same list prices, half the cache-read price), and the decision record notes cost per passed task and pass rate for each pair.
   A role changes only if the newer model's pass rate is no worse.
