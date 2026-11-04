# Decision Record 2026-10-23: tile-laying-game Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-tile-laying-game](../../specs/SPEC-2026-09-30-tile-laying-game.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-tile-laying-game.md): "Tile Towns", a two-player, one-device tile-laying game on the base game's tournament rules, with a seeded, balanced tile set each game and a plain JSON game file that saves and loads any position.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
A static page with no server, database, or account; deterministic for a seed and move list; no publisher name, art, or rulebook text.

### Nice to haves

#### Functional

A rematch on the same set with seats swapped; a note of who scored what after each move.

#### Non-functional

Tiles drawn by the same geometry that decides their features, so the picture can't disagree with the scoring.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Bots, online play, expansions, timers, more than two players, undo.

#### Non-functional

A game engine, a UI framework, or a server-side store.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
There is no old repo to restart.
Following the [languages decision](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md), browser code stays TypeScript: modules tested and bundled by Bun into one script, with no runtime dependencies, drawn on a canvas.
- **Tiles** (`src/tiles.ts`): a tile is a short code of four edge letters clockwise from the top (N, E, S, W), each `C` (city), `R` (road), or `F` (field), plus flags: `+M` monastery, `+S` shield, `+J` roads end at a junction, `+X` each city edge is its own city, `+D` two roads both end in the city.
  Without flags, all city edges form one city, two road edges are one road, and a single road ends in the city or monastery.
  For example `CRFR` is the start tile (city on top, road across) and `FRRR+J` a three-way junction.
  This is shorter than JCloisterZone's per-feature descriptions, at the cost of only describing the tile layouts the grammar allows; that is all the generator needs.
  A geometry function says what is at every point of a tile; rasterizing it at 48x48 finds the fields (split by cities and roads), which cities each field touches, and an anchor point per feature for meeples.
  A code is a valid layout only if every city and road is in one piece, meets exactly its own edges, roads cross nothing and end only at a city, monastery, or junction, separate cities don't touch, and no field is shut away from every edge.
  `catalog()` lists every valid layout up to rotation (37 today).
- **Generator** (`src/generate.ts`): mulberry32 seeded random numbers draw 71 tiles from the catalog, weighted by the base set's counts with a small weight for every other valid layout, plus the start tile, and redraw the whole set until it is within the balance limits; then the draw order is shuffled.
  Limits against the base set: each edge type's share within 0.03, 5 to 7 monasteries, 8 to 12 shields, tiles that end a road within 3 of 13, and tiles with a one-edge city (which closes a city) within 4 of 23.
  The base set used as the reference is the commonly listed A to X distribution (A2 B4 C1 D4 E5 F2 G1 H3 I2 J3 K3 L3 M2 N3 O2 P3 Q1 R3 S2 T1 U8 V9 W4 X1).
  A library catalogue record confirms A to D; the rest are as commonly listed and were not checked against a rulebook, which only moves the balance target slightly.
- **Rules engine** (`src/engine.ts`): pure functions over a plain JSON `State` (board, meeples, scores, both hands, deck, discards, turn, starter, over).
  `apply(state, move)` returns the next state or the reason the move is illegal; `placements`, `meepleSpots`, and `legalMoves` list what is legal.
  Features are found by union-find over each placed tile's features, joined across matching edges (fields across matching thirds of an edge), recomputed from the board when needed: 72 tiles make this cheap, and it keeps the state free of derived data.
  Each player holds one visible tile; a tile with no legal placement is set aside and another drawn; finished roads, cities, and monasteries score at once; after the last tile, the end scoring runs; on a tied score the starting player loses.
- **Game file** (`src/file.ts`): JSON with `format` (`tile-laying-game/1`), `seed` (`null` for a hand-made set), `tiles` (the start tile, then the draw order), `starter`, `moves` (`{x, y, r, meeple}`, where `meeple` is `null` or a feature of the tile in its own numbering such as `city0`, `road1`, `field2`, `monastery`), and `state` (the snapshot).
  Loading replays the moves from the tiles and refuses the file unless that gives the snapshot; a file with a snapshot and no moves loads at that position after a sanity check, so a position can be written by hand.
- **Page** (`src/app.ts`, `src/draw.ts`, `public/`): one canvas for the board, fitted to the board plus the legal spots; click a spot, rotate (R), click a circle to add a meeple, then place (Enter).
  Tiles are drawn pixel by pixel from the same geometry the rules use.
- **Commands**: `bun run build` bundles into `dist/`; `bun run serve` builds and serves it with a small `Bun.serve` script, so nothing is installed globally.
  Publishing on Pages is not in the spec, so the Site workflow does not build it yet.

### High-level C4(context/container/component/code) diagram

```text
clicks / keys --> app.ts --> file.ts (game: tiles, seed, moves, state) --> engine.ts (apply, legalMoves) --> tiles.ts (features)
                    |                                                                                          ^
                    +--> draw.ts (tile pictures from the same geometry) -----------------------------------------+
generate.ts (seed --> 72 balanced tiles) --> file.ts start()
Save/Load: file.ts save() / load() (replays moves and checks the snapshot)
```

### Choices and Tradeoffs/Risks

A geometry-defined tile over a hand-listed feature table: the generator can make layouts no one listed, and the drawing can't disagree with the scoring; the cost is a rasterizing pass per tile kind, cached.

Recomputing features from the board over storing a union-find in the state: the file stays small and hand-writable, and a hand-written position needs no derived data; the cost is redoing a few hundred unions per check, well under a frame.

Rejection sampling over a constrained solver: simple and obviously within the limits; about 5 ms a set.

### Dependencies

None at runtime. Bun, Biome, and TypeScript at development time, from the template.

### Interfaces

The game file above is the only external interface; its `format` string changes if the shape does.

## Key Results and retrospective feedback

28 tests cover each scoring rule, features merging across tiles, shared and outright majorities, end scoring, illegal moves, set-aside tiles, ties, whole random games, the generator's validity and balance over 100 seeds, and save, load, and hand-written files.
A browser run played a full 71-move game through the page's clicks and keys, saved mid-game, and loaded it back to the same state.
