# SPEC-0006: Connect6 Rebuild

Restarts [dijonkitchen/connect](https://github.com/dijonkitchen/connect) in `projects/connect6/`, per [Projects in ageone](../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `docs/decisions/connect6/`.

A spec-driven Connect6 game (19×19, Black opens with one stone, then two per turn, six or more in a row wins) with a pure engine, pluggable agents, and a web UI, rebuilt here with stronger agents so it doubles as an agent benchmark.

## Functional requirements

- A pure engine: immutable game state, move legality, and win detection, with no DOM, network, or clock, carrying over the old repo's acceptance criteria.
- A player interface with random and heuristic baselines, an MCTS player that treats the two-stone turn as one move, and an LLM player that picks its model by role through the model roles config from [SPEC-0002](../SPEC-0002-vendor-neutral-ai-harness.md), never a model ID in code.
  An illegal or unparseable LLM reply is retried a bounded number of times, then counted as a forfeit.
- A web UI where either side can be a person or any player, behind an async game client interface so a network back end can drop in later.
- A headless tournament command that plays players against each other over seeded games, swapping colors, and writes one NDJSON line per game (players, winner, moves, time, and for LLM players, tokens and cost) that [SPEC-0004](../SPEC-0004-eval-benchmark-pages.md) can publish.

## Non-functional requirements

- The engine has no runtime dependencies and checks a win in time proportional to the stones near the move, not the whole board.
- Reproducible: the same seed and non-LLM players give the same games.
- Cheap: the LLM player defaults to the `cheap` role, and tournaments print an estimated cost first.

## Definition of done

1. The first decision record in `docs/decisions/connect6/` chooses the stack (old: TypeScript, Bun, Biome, Vite, vanilla UI).
2. `projects/connect6/` is set up by `make`, and its CI job passes on `main`.
3. The engine passes tests covering every rule, each citing its acceptance criterion.
4. The MCTS player beats the heuristic player in at least 80% of 100 seeded games, alternating colors.
5. The LLM player finishes games in the UI and the tournament with no crashes from bad replies, and tournament results appear on the SPEC-0004 pages.
