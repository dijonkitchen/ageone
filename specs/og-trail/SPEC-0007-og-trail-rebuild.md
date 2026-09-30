# SPEC-0007: OG Trail Rebuild

Restarts [dijonkitchen/og_trail](https://github.com/dijonkitchen/og_trail) in `projects/og-trail/`, per [Projects in ageone](../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `docs/decisions/og-trail/`.

The Oregon Trail for modern life (rent, student loans, burnout, 2,000 miles to Stability), rebuilt here with agent players so it doubles as a long-horizon eval.

## Functional requirements

- One engine behind a `view()`/`submit(value)` protocol: each view has a phase, text, choices, and an input type; invalid input leaves the game unchanged.
- The game content of the old repo: three professions with score multipliers, a store, weekly hustle and budget choices, rent, health, random events, landmarks, and endings.
- Save and resume, including the random state: same seed and inputs give the same story on any frontend.
- A terminal frontend and a browser frontend over a small JSON HTTP API.
- Players over the protocol: random, rule-based, and an LLM player that picks its model by role through the model roles config from [SPEC-0002](../SPEC-0002-vendor-neutral-ai-harness.md), never a model ID in code; invalid answers are shown back once, then a fallback choice is taken and counted.
- A batch command that runs players over seeded games headless and writes one NDJSON line per game (player, seed, profession, outcome, score, weeks, tokens, cost) that [SPEC-0004](../SPEC-0004-eval-benchmark-pages.md) can publish.

## Non-functional requirements

- The engine has no runtime dependencies; the LLM player is an optional extra.
- Adding an event or landmark is data only, and every one is exercised by the tests automatically.
- Cheap: the LLM player defaults to the `cheap` role and a few seeds.

## Definition of done

1. The first decision record in `docs/decisions/og-trail/` chooses the stack (old: Python 3.11+, uv, ruff, pytest, stdlib HTTP).
2. `projects/og-trail/` is set up by `make`, and its CI job passes on `main`.
3. Playthroughs work in the terminal and the browser, and a saved game resumes identically.
4. Random, rule-based, and LLM players each finish 20 seeded games per profession, and the rule-based player reaches Stability more often than random.
5. Batch results appear on the SPEC-0004 pages.
