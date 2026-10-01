# SPEC-0005: Tile-Laying Game

## Functional requirements

A turn-based tile-laying game in the style of Carcassonne, playable in the browser by people and by agents, with our own name, art, and tile set.

- **Board**: an open, unbounded grid that grows as tiles are placed, starting from one fixed start tile.
- **Tiles**: square tiles whose four edges are each city, road, or field, and whose center can hold a monastery.
  A tile set is a plain data file in the repo listing each tile's edges, internal connections, special features (such as a shield on a city), and count.
  The base set has 72 tiles, matching the shape of the classic game's distribution.
- **Turn**: draw a random tile from a seeded bag, place it next to at least one placed tile so every touching edge matches, rotating it in 90° steps, then optionally place one meeple on a feature of that tile.
  A meeple can't go on a city, road, or field already holding a meeple, counting every tile that feature reaches.
  A tile with no legal placement is set aside and another drawn.
- **Scoring** when a feature completes, returning its meeples to their owners:
  - Road: 1 point per tile.
  - City: 2 points per tile and per shield.
  - Monastery: 9 points once surrounded by eight tiles.
  - A completed feature's points go to the player or players with the most meeples on it; ties all score in full.
- **End of game**: after the last tile, incomplete roads and cities score 1 point per tile and shield, incomplete monasteries 1 point per tile in and around them, and each field 3 points per completed city it touches, to the majority holder.
- **Players**: 2 to 5, each with 7 meeples.
  Each seat is a person (hotseat on one device), a built-in bot, or an agent.
- **Rules engine**: one pure module that, given a game state and a move, returns the next state or a reason the move is illegal, and lists the legal moves for the current player.
  The UI, the bots, and the agent interface all go through it; nothing else changes game state.
- **Agent interface**: an AXI-style CLI ([Agent Tool Interfaces](../docs/decisions/2026-09-27-agent-tool-interfaces.md)) to start a game, show the state, list legal moves, and make a move, so an agent harness can play a seat.
  State is shown in a compact text form an agent can read, not only as pixels.
- **Built-in bot**: a greedy bot that picks the move with the best immediate score change, as an opponent for people and a baseline for agents.
- **Replays**: a game is saved as its seed, tile set, and move list in one file, and replays to the same final state and scores.
- **UI**: draws the board, the current tile with its legal spots highlighted, rotation, meeple placement, scores, remaining tile count, and a log of moves; pan and zoom the board.

## Non-functional requirements

- Simple: a static web page with no server, database, or account; a game in progress lives in the browser and can be exported as a replay file.
  Online multiplayer is out of scope.
- Original: no Carcassonne name, logo, art, or rulebook text; tiles are drawn by code or our own assets.
  Game mechanics are not copyrighted, but the brand is the publisher's.
- Correct: the rules engine is covered by tests, including each scoring rule, feature merging across tiles, shared majorities, and end-of-game scoring, plus property tests that random legal games always end with conserved meeples and non-negative scores.
- Deterministic: the same seed and moves always give the same game, so bugs, bot games, and agent games reproduce exactly.
- Readable: works at phone width with touch, in light and dark themes, and with keyboard controls for placing and rotating.
- Runs in the pinned environment from [SPEC-0003](SPEC-0003-make-setup.md), with no global installs.

## Definition of done

1. The rules engine, base tile set, and greedy bot exist with tests covering every rule above, and those tests run in CI.
2. Two people can play a full game hotseat in the browser, and one person can play a full game against one or more bots.
3. An agent harness plays a full game against the greedy bot through the CLI, and the game is saved as a replay that reloads to the same final scores.
4. One command builds the static site, and one command starts it locally.
5. A decision record states the stack chosen for the game.
