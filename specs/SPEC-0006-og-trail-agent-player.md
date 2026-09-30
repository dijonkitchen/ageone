# SPEC-0006: OG Trail Agent Player

## Repo

[dijonkitchen/og_trail](https://github.com/dijonkitchen/og_trail), a Python text game with one engine behind a `view()`/`submit()` protocol and a JSON HTTP API.
See [Project Repos](../docs/decisions/2026-09-30-project-repos.md).

## Functional requirements

Let agents play OG Trail, so the game becomes a long-horizon eval case: many turns of budgeting under random events, with a clear score.

- A player interface over the existing protocol: given the current `View`, return a value to `submit`.
  Built-in players: a random baseline and a simple rule-based player.
- An LLM player that picks a model by `provider/model` ID through the model roles from [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md), reads each view as text, and answers with a choice id or value.
  Invalid input is shown back once, then a fallback choice is taken and counted.
- A batch command, `og-trail play --player <name> --seeds N`, that runs games headless and writes one NDJSON line per game: player, seed, profession, outcome (reached Stability or how it ended), score, weeks, and for LLM players, tokens and cost.
- Game logs are replayable: seed plus inputs reproduce the run on any frontend, as today.

## Non-functional requirements

- The engine keeps no runtime dependencies; the LLM player is an optional extra.
- Cheap: the LLM player defaults to the `cheap` role and a small number of seeds.
- Existing CI (ruff and pytest on Python 3.11 to 3.13) stays green.

## Definition of done

1. Random, rule-based, and LLM players each finish 20 seeded games per profession through the batch command.
2. The rule-based player reaches Stability more often than the random player.
3. Results are NDJSON that [SPEC-0004](SPEC-0004-eval-benchmark-pages.md) can publish, and the README documents the command.
4. Tests cover the player interface and the batch command, and CI passes.
