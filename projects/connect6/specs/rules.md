# Connect6 — Rules and acceptance criteria

Carried over from [dijonkitchen/connect](https://github.com/dijonkitchen/connect)'s `specs/connect6.spec.md` (2026-05-24), extended 2026-10-04 for [SPEC-2026-09-30-connect6-rebuild](SPEC-2026-09-30-connect6-rebuild.md) with MCTS and LLM players and the tournament.

## 1. Overview

Connect6 is a two-player connection game played on the intersections of a
Go board. Black and White alternate turns. After Black's opening single
stone, each turn places **two** stones. The first player to form a line of
**six or more** of their own stones — horizontally, vertically, or
diagonally — wins.

This document is the source of truth for game behaviour. Acceptance
criteria use [EARS](https://alistairmavin.com/ears/) phrasing and carry
stable IDs. Tests reference these IDs (see `test/`).

## 2. Domain glossary

| Term       | Meaning                                                             |
| ---------- | ------------------------------------------------------------------- |
| Board      | A `size`×`size` grid of intersections. Default `size = 19`.         |
| Position   | A `{ row, col }` coordinate, both in `[0, size)`.                   |
| Cell       | The content of a position: `"black"`, `"white"`, or empty (`null`). |
| Player     | A colour: `"black"` or `"white"`. Black moves first.                |
| Move       | The set of positions a player fills on a single turn.               |
| Run        | Maximal sequence of same-colour stones along one of four axes.      |
| Win length | Run length that wins the game: **6**.                               |

## 3. Functional requirements

### REQ-BOARD — Board setup

- **AC-BOARD-1** — WHEN a new game is created, THE SYSTEM SHALL produce a
  `size`×`size` board (default 19×19) in which every cell is empty.
- **AC-BOARD-2** — WHEN a new game is created, THE SYSTEM SHALL set the
  player to move to `"black"`.

### REQ-TURN — Turn structure

- **AC-TURN-1** — WHEN no move has yet been played, THE SYSTEM SHALL
  require the moving player to place **exactly one** stone (Black's
  opening move).
- **AC-TURN-2** — WHEN at least one move has been played, THE SYSTEM SHALL
  require the moving player to place **exactly two** stones.
- **AC-TURN-3** — AFTER a player completes a legal move that neither wins
  nor draws, THE SYSTEM SHALL pass the turn to the opponent.
- **AC-TURN-4** — THE SYSTEM SHALL maintain a `moveCount` equal to the
  number of completed moves, used to derive the required stone count via
  AC-TURN-1 / AC-TURN-2.

### REQ-MOVE — Move legality

- **AC-MOVE-1** — THE SYSTEM SHALL reject a move whose number of positions
  is not the required count (1 opening, otherwise 2).
- **AC-MOVE-2** — THE SYSTEM SHALL reject a move containing a position
  outside the board bounds.
- **AC-MOVE-3** — THE SYSTEM SHALL reject a move targeting a cell that is
  already occupied.
- **AC-MOVE-4** — THE SYSTEM SHALL reject a move that targets the same
  position more than once within the move.
- **AC-MOVE-5** — WHEN a move is legal, THE SYSTEM SHALL place every stone
  for the moving player and return a new state, leaving the input state
  unchanged (immutability).

### REQ-WIN — Win detection

- **AC-WIN-1** — WHEN, after a move, the moving player has a run of **six
  or more** stones horizontally, vertically, or on either diagonal, THE
  SYSTEM SHALL declare that player the winner and end the game.
- **AC-WIN-2** — WHEN a player wins, THE SYSTEM SHALL expose the winning
  line (the list of positions forming the run) for highlighting.
- **AC-WIN-3** — A run **longer** than six (an "overline") SHALL also win;
  there is no overline restriction in Connect6.
- **AC-WIN-4** — Win detection SHALL consider only stones placed during
  the move's own turn as the trigger, but a run may be completed using any
  combination of the moving player's stones on the board.

### REQ-END — Game termination

- **AC-END-1** — WHEN the board has no empty cell and no player has met the
  win condition, THE SYSTEM SHALL declare a draw.
- **AC-END-2** — WHEN fewer empty cells remain than the required stone
  count and no win is possible to complete, THE SYSTEM SHALL declare a
  draw rather than allow an under-filled move.
- **AC-END-3** — WHEN the game has ended (won or drawn), THE SYSTEM SHALL
  reject any further move.

### REQ-PLAYERS — Pluggable players

- **AC-PLAYERS-1** — THE SYSTEM SHALL define an `Agent` interface
  (`chooseMove(state) -> Promise<Move>`) so that human and programmatic
  players are interchangeable.
- **AC-PLAYERS-2** — Any `Agent` SHALL return only legal moves for the
  given state (legality defined by REQ-MOVE).
- **AC-PLAYERS-3** — A provided heuristic agent SHALL, when a move exists
  that immediately wins, choose such a move.
- **AC-PLAYERS-4** — A provided heuristic agent SHALL, when the opponent
  has a single-ended immediate winning threat and no winning move exists
  for itself, place a stone that blocks that threat.
- **AC-PLAYERS-5** — A provided MCTS agent SHALL search whole turns (both
  stones of a turn as one move), SHALL take a win available this turn, and
  SHALL block every opponent window that the opponent could fill on its
  next turn when one move can.
- **AC-PLAYERS-6** — WHEN given the same seed and state, the random and
  MCTS agents SHALL choose the same move.
- **AC-PLAYERS-7** — An LLM agent SHALL take its model through an injected
  chat function chosen by role, SHALL show an illegal or unparseable reply
  back to the model with the reason, and AFTER a bounded number of replies
  SHALL forfeit instead of crashing.
- **AC-PLAYERS-8** — WHEN a player forfeits or returns an illegal move, THE
  SYSTEM SHALL end the game with the opponent as the winner.

### REQ-TOURNAMENT — Headless tournament

- **AC-TOURNAMENT-1** — THE SYSTEM SHALL play every pair of the given
  players over seeded games, swapping colours each game.
- **AC-TOURNAMENT-2** — THE SYSTEM SHALL write one NDJSON line per game
  with the players, winner, reason, moves, time, and each side's tokens and
  cost.
- **AC-TOURNAMENT-3** — WHEN no LLM player takes part, the same seed SHALL
  give the same games.
- **AC-TOURNAMENT-4** — WHEN an LLM player takes part, THE SYSTEM SHALL
  print an estimated cost before the first game.

### REQ-CLIENT — Transport abstraction

- **AC-CLIENT-1** — THE SYSTEM SHALL define an async `GameClient`
  interface (`getState`, `applyMove`, `reset`) so the frontend is agnostic
  to whether the engine runs in-memory or behind a network backend.
- **AC-CLIENT-2** — The in-memory `LocalGameClient` SHALL implement
  `GameClient` over the pure core and SHALL reject illegal moves with the
  same reasons as the core.

## 4. Non-functional requirements

- **NFR-1 (Maintainability)** — The core is pure TypeScript with no
  runtime dependencies and is exercised by tests traceable to the ACs
  above.
- **NFR-2 (Type safety)** — `tsc --noEmit` (strict) passes; `any` and
  non-null assertions are disallowed in `src/core`.
- **NFR-3 (Extensibility)** — Adding a networked backend requires only a
  new `GameClient` implementation; no change to core or UI logic.
- **NFR-4 (Performance)** — A move is applied and checked for a win in
  time proportional to the stones placed and the board's win-length
  window, not the whole board, so play stays responsive on 19×19.

## 5. Out of scope (for this iteration)

- Networked multiplayer backend (the seam exists; the server does not).
- Game persistence, accounts, ELO/ratings, time controls, swap/balance
  opening rules (e.g. pro/long-pro openings).

## 6. Traceability

Each acceptance criterion ID appears in at least one test name under
`test/`. Run `bun test` to execute the spec.
