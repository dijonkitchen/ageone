# SPEC-0005: Connect6 Agents

## Repo

[dijonkitchen/connect](https://github.com/dijonkitchen/connect), following its `AGENTS.md`: spec-first with EARS acceptance criteria, TDD, pure `src/core`, and Bun.
See [Project Repos](../docs/decisions/2026-09-30-project-repos.md).

## Functional requirements

Stronger players for the Connect6 game, and a way to measure them, so it doubles as an agent benchmark.

- An MCTS agent implementing the existing `Agent` interface, searching the two-stone turn as one move, with a time or playout budget.
- An LLM agent implementing `Agent`, choosing a model by `provider/model` ID through the model roles from [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md).
  It gets the board in a compact text format, and an illegal or unparseable reply is retried a bounded number of times and then counted as a forfeit.
- A headless tournament command that plays agents against each other over many seeded games, swapping colors, and writes one NDJSON line per game (agents, winner, moves, time, and for LLM agents, tokens and cost).
- The web UI can pick any agent for either side.
- New acceptance criteria in `specs/connect6.spec.md` cover each agent and the tournament, and each test names its criterion.

## Non-functional requirements

- `src/core` gains no runtime dependencies; the LLM agent is an edge, outside the core.
- Reproducible: the same seed and agents give the same games for the non-LLM agents.
- Cheap: the LLM agent defaults to the `cheap` role; tournaments print an estimated cost before running.

## Definition of done

1. The MCTS agent beats the heuristic agent in at least 80% of 100 seeded games, alternating colors.
2. The LLM agent completes games in the UI and the tournament with no crashes from bad replies.
3. The tournament command writes NDJSON results that [SPEC-0004](SPEC-0004-eval-benchmark-pages.md) can publish.
4. `bun run check`, `bun run typecheck`, `bun test`, and `bun run build` pass, and an ADR in `docs/adr/` records the agent choices.
