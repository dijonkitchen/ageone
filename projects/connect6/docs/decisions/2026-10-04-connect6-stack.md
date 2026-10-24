# Decision Record 2026-10-04: connect6 Stack

## Status timeline

2026-10-04: Proposed by Claude, implementing [SPEC-2026-09-30-connect6-rebuild](../../specs/SPEC-2026-09-30-connect6-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-connect6-rebuild.md) that runs a pure Connect6 engine, random, heuristic, MCTS, and LLM players behind one `Agent` interface, a web UI where either side is a person or any player, and a headless tournament writing NDJSON.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
No runtime dependencies for the engine; the LLM player's API key stays out of the browser.

### Nice to haves

#### Functional

A network game back end can replace the in-memory `GameClient` without UI changes.

#### Non-functional

Fast enough that 100 seeded MCTS games run in a couple of minutes on a laptop.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Opening balance rules, ratings, accounts, and a hosted multiplayer server.

#### Non-functional

A UI framework or a separate bundler for one page.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo's stack (TypeScript, Bun, Biome, Vite, vanilla UI) mostly holds; Vite is dropped because Bun's own HTML bundler and `Bun.serve` cover the dev server and the build, so the project has no dependencies beyond Biome, TypeScript, and Bun's types.

- **Engine**: carried over from the old repo, `src/core/` (`types`, `board`, `rules`, `game`, `client`), pure functions over immutable `GameState`.
  Its acceptance criteria moved to [`specs/rules.md`](../../specs/rules.md), extended for the new players and the tournament, and a test checks that every criterion is cited by a test name.
  The draw check now counts stones from `moveCount` instead of scanning the board.
- **Players**: `src/core/agents/`. Random and heuristic carry over; MCTS and LLM are new.
  MCTS searches whole turns on a private flat board that keeps per-window stone counts, so wins, threats, and cell scores are cheap.
  The LLM player takes its model call as an injected `Chat` function, so the core stays free of network code.
- **Edges**: `src/cli/openrouter.ts` reads the model for a role from the root [`harness/models.json`](../../../../harness/models.json) and calls OpenRouter with `fetch` and the config's routing settings; `src/cli/server.ts` serves the UI and proxies the browser LLM player's calls; `src/cli/tournament.ts` runs games headless.
- **UI**: the old vanilla TypeScript UI, with MCTS and LLM options, forfeits shown, and a stale-loop guard so changing players mid-game can't interleave two games.

### High-level C4(context/container/component/code) diagram

```text
browser (index.html, src/ui) ─> GameClient (in memory) ─> engine (src/core)
browser LLM player ─> POST /api/chat (src/cli/server.ts) ─> OpenRouter (role from harness/models.json)
bun run tournament (src/cli/tournament.ts) ─> players (random, heuristic, mcts, llm) ─> engine ─> NDJSON lines ─> eval pages
```

### Choices and Tradeoffs/Risks

- MCTS uses tactics from window counts plus short noisy-greedy rollouts scored by window potential, not random playouts to the end, which are slow and nearly meaningless on 19×19.
  With 300 playouts a turn it won 100 of 100 seeded games against the heuristic player, 50 as each colour, in about two minutes ([results](../../results/2026-10-04-mcts-vs-heuristic.ndjson)); CI checks a cheaper 10-game version.
- The LLM player is stateless per turn (board, last move, and the stones to place), which keeps cost flat and avoids long contexts; a bad reply is shown back with the reason, at most three replies a turn, then it forfeits.
- A forfeit or illegal move ends the game in the runner (`src/match.ts`), not the engine, so the engine's rules stay the game's rules.

### Dependencies

None at runtime; Biome, TypeScript, and `@types/bun` for development.

### Interfaces

- `Agent.chooseMove(state) -> Promise<Move>`, throwing `ForfeitError` when a player gives up; `Agent.usage` for token and cost counts.
- `GameClient` (`getState`, `applyMove`, `reset`), with `LocalGameClient` in memory.
- `POST /api/chat` with `{ role, messages }`, answering `{ content, tokens, cost }`.
- `bun run tournament --players a,b[,c] --games N --seed S [--size 19] [--iterations 300] [--role cheap] [--out file]`.

## Key Results and retrospective feedback
