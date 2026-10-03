# SPEC-2026-09-30-tile-laying-game: Tile-Laying Game

## Functional requirements

A two-player, turn-based tile-laying game in the style of Carcassonne, played on one device, following the tournament rules of the base game, with a freshly generated tile set each game.

- **Board**: an open grid that grows as tiles are placed, starting from the start tile.
- **Tiles**: square tiles whose four edges are each city, road, or field, with internal connections between edges, and optionally a monastery in the center or a shield on a city.
- **Generated tile sets**: each game generates its own set of 72 tiles (including the start tile) from a seed, instead of using the fixed base set.
  - Every generated tile is a valid layout: edges of the same feature are either connected or clearly separate, a road with other than two ends stops at a junction, and fields are split by the roads and cities that cross them.
  - The set as a whole stays close to the base game's balance: the share of city, road, and field edges, the number of monasteries and shields, and the share of tiles that end roads or close cities, so games feel familiar and stay playable.
  - Both players draw from the same generated set, and the seed is saved, so the same set can be replayed with the players' seats swapped.
- **Rules**: the base game as played at tournaments (such as the [German Carcassonne championship rules](https://carcassonne-meisterschaft.de/en/tournamentrules.htm)), with no expansions:
  - Two players with 7 meeples each.
  - On your turn, place your tile next to at least one placed tile so every touching edge matches, rotating it in 90° steps, then optionally place one meeple on a feature of that tile that no meeple already occupies, counting every tile the feature reaches.
    A tile with no legal placement is set aside and another drawn.
  - At the end of your turn you draw your next tile, which both players can see during your opponent's turn.
  - A completed road scores 1 point per tile, a city 2 per tile and per shield, and a monastery 9 once surrounded; its meeples return to their owners.
    The player with the most meeples on a feature scores it, and tied players both score in full.
  - After the last tile, incomplete roads and cities score 1 point per tile and per shield, incomplete monasteries 1 point per tile in and around them, and each field 3 points per completed city it touches, to the player with the most meeples on it.
  - Players alternate who starts across games.
    If the scores tie, the starting player loses.
- **Rules engine**: one pure module that, given a game state and a move, returns the next state or a reason the move is illegal, and lists the legal moves.
  The UI goes through it; nothing else changes game state.
- **Game file**: a game saves to and loads from one plain-text JSON file holding the tile set, the seed, the move list, and a snapshot of the current state (board, meeples, scores, tiles left in order, whose turn).
  Loading a file resumes the game at that state, so a file can also set up a position by hand, for tests or puzzles.
  Loading checks that replaying the moves gives the snapshot, unless the file has a snapshot and no moves.
  Tiles are written in a short text code (for example `CcRrF` style edge letters, as in JCloisterZone) so files stay readable and diffable.
- **UI**: draws the board, the current and next tile, the legal spots for the current tile, rotation, meeple placement, scores, meeples left, tiles left, and buttons to save and load a game file.

## Non-functional requirements

- Simple: a static web page with no server, database, or account.
  No bots, agents, online play, expansions, timers, or more than two players for now.
- Original: no Carcassonne name, logo, art, or rulebook text; tiles are drawn by code.
  Game mechanics are not copyrighted, but the brand is the publisher's.
- Correct: the rules engine and the tile generator are covered by tests, including each scoring rule, features merging across tiles, shared majorities, end-of-game scoring, and that every generated tile is valid and every generated set meets the balance limits.
- Deterministic: the same seed and moves always give the same game.
- Runs in the pinned environment from [SPEC-2026-09-26-make-setup](SPEC-2026-09-26-make-setup.md), with no global installs.

## Definition of done

1. The rules engine and tile generator exist with tests covering the rules and limits above, and those tests run in CI.
2. Two people can play a full game on one device in the browser with a generated tile set, ending with the correct final score.
3. A game saved mid-way loads back to the same state and plays on to the same result, and a hand-written game file loads at the position it describes.
4. One command builds the static page, and one command starts it locally.
5. A decision record states the stack and the game file format.
