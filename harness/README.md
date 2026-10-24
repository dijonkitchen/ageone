# Harness

How agentic work in this repo reaches a model, as decided in [Vendor-Neutral AI Harness](../docs/decisions/2026-09-26-vendor-neutral-ai-harness.md).

## Files

- [`models.json`](models.json): the one place models are chosen.
  `roles` maps `default`, `cheap`, `frontier`, and `judge` to `provider/model` IDs; `openRouter` holds the privacy settings and the US and EU host allowlist for open-weight models; `harnesses` pins each harness's version.
- [`web-search.json`](web-search.json): settings for the [pi-web-access](https://github.com/nicobailon/pi-web-access) extension, pinned to Exa (keyed with `EXA_API_KEY`, keyless otherwise).
- [`../.pi/settings.json`](../.pi/settings.json): pi's project settings, holding the `default` role and the web search package; `harness/sync` writes the `default` role and keeps the other keys, so the package pin is edited by hand.
- `config.mjs`, `sync`, `pi`: the scripts below.

## Use

```sh
export OPENROUTER_API_KEY=...          # the default route for every role
harness/sync --agent-dir ~/.pi/agent   # once: OpenRouter privacy, host allowlist, and web search settings for your pi
harness/pi                             # the pinned pi, on the default role
harness/pi --model openrouter/deepseek/deepseek-v4.1-flash -p "..."   # any other model, by provider/model ID
```

pi asks to trust the project the first time, because `.pi/settings.json` installs the web search extension.

## Change a model

1. Edit the role in `models.json`, using an ID from `harness/pi --list-models`.
2. Run `harness/sync`, which mirrors `default` into `.pi/settings.json`; CI fails when they disagree.
3. Run the evals on the new model before relying on it ([evals](../evals/README.md)).

An open-weight model gets the host allowlist only when its ID is in `openRouter.openWeightModels`.
Go direct to a vendor by changing the provider: `anthropic/claude-sonnet-5` with `ANTHROPIC_API_KEY` instead of `openrouter/anthropic/claude-sonnet-5`.

## Account settings to set by hand

`models.json` sends zero data retention and `data_collection: "deny"` on every OpenRouter request, and pins open-weight models to the allowlist.
As a backstop for tools that bypass it, also turn on zero data retention in OpenRouter's privacy settings and add the China-based hosts (such as DeepSeek, Moonshot, Z.AI, MiniMax, Alibaba, Baidu, SiliconFlow, and StreamLake) to its ignored providers.
