# Decision Record 2026-10-23: algorithm-roguelike Stack

## Status timeline

2026-10-23: Proposed by Claude (scheduled spec run), for JC's review in the pull request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-algorithm-roguelike.md): a turn-based grid roguelike in the browser where each algorithm learned (by puzzle or by code) becomes part of the game, starting with all of tiers 1 and 2.

#### Non-functional

- Installable in the pinned environment from the root `make`, with `make check` passing in CI.
- Nothing to install for players, keyboard-only play, and ASCII graphics.
- Deterministic runs.
- Player code sandboxed with time and memory limits.

### Nice to haves

#### Functional

- Tiers 3 and 4 later, each only a new folder.
- Shareable replays.

#### Non-functional

- A small first load, with the code sandbox fetched only when needed.

### Avoid out of scope runaway rabbit hole risks

#### Functional

- Tile art, sound, or a level editor.
- A second code-mode language.

#### Non-functional

- A game framework or UI framework.
- A server: everything runs in the page.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
There is no old repo to restart.
- **Language**: TypeScript on Bun for the engine, concepts, and page, with strict types and no UI framework.
  The engine core (`src/core/`) is plain functions over a JSON-able `State`, so tests run it without a browser.
- **Rendering**: ASCII in a `<pre>`, one `<span>` per lit cell, colored from the Okabe-Ito palette.
  Every thing on the map also has its own glyph, so color is never the only cue.
  A text size control scales the whole page.
  An `aria-live` message log and a spoken summary of what is in sight serve screen readers.
- **Determinism**: all randomness comes from one mulberry32 state stored in the run (`State.rng`).
  A run is its seed, the concepts learned before it, and its inputs.
  Learning a concept mid-run is itself an input (`learn:<id>`), so a replay reproduces it.
  The page saves the current run that way and replays it on reload; with the seeded PRNG concept, players can save and load replay files.
- **Concepts as plugins**: each concept is a folder under `src/concepts/` with its reference implementation, unit tests, lesson, puzzle, and hooks.
  The engine never names a concept; a test enforces this.
  It asks the unlocked concepts for hooks: a floor generator, vision, memory (fog of war), a turn scheduler, a monster brain, loot, the pack's rules, page features, and player actions.
  Where several concepts offer one kind, the highest priority wins.
  See [Adding a concept](../adding-a-concept.md).
- **Puzzle mode**: each trial is a list of multiple-choice steps generated from the reference implementation's own trace for a seed, so every answer is the reference's answer.
  A trial passes within a set number of mistakes; a failed one starts again with a new seed.
- **Code-mode sandbox**: player JavaScript runs in [QuickJS](https://bellard.org/quickjs/) compiled to WebAssembly, through `quickjs-emscripten` 0.32 (MIT).
  - QuickJS is a separate interpreter with its own heap and no host objects: no `fetch`, storage, DOM, timers, or `require`.
  - Arguments and results cross as JSON copies, so player code can't touch the game's objects.
  - Each runtime has a 16 MB memory cap and an interrupt handler that stops a call after 250 ms.
  - It runs synchronously, so the engine stays synchronous and deterministic; a Web Worker would have made every hook asynchronous.
  - A trial's suite is the same one the reference passes, both directly and as source inside the sandbox; a test checks both.
  - In the game, a call that throws, times out, or returns something unusable falls back to the reference for the rest of the run and switches the player's code off, so player code never ends a run.
  - Code mode covers BFS (room reveal), the binary heap (the turn scheduler), and Bresenham lines (thrown darts).
- **Build**: `bun run build` bundles to `dist/` with code splitting.
  The game loads about 120 kB of script, and the 1.2 MB QuickJS chunk loads in the background.
  `bun run serve` builds and serves on `PORT` (default 8080).
  The page's content security policy allows only its own files, plus `wasm-unsafe-eval` for QuickJS.
- **Storage**: `localStorage` keeps what was learned, the player's passing code, the text size, and the current run.
  Every read and write is guarded, so the game works without storage.

### High-level C4(context/container/component/code) diagram

```text
browser page (src/ui)
  app.ts ── keys, map, dialogs ──► core/engine.ts (State, step, replay) ◄── hooks ── concepts/<id>/index.ts
  lesson.ts ── lessons, puzzle trials, code editor ──► core/sandbox.ts ── QuickJS (WebAssembly) ── player code
  store.ts ── localStorage (learned concepts, code, current run)
```

### Choices and Tradeoffs/Risks

- **QuickJS over a Web Worker or an iframe sandbox**:
  - It gives a real memory cap and a synchronous call.
  - The time limit is checked between bytecode steps, so one huge native call can overrun it. In a test, filling arrays of 100,000 items past the memory cap took about 5 s before failing.
  - Such a failure happens at most once, because failed code is switched off.
- **Puzzle answers from traces, not hand-written**: every puzzle is correct by construction and new each attempt, but the prompts are templates rather than hand-crafted stories.
- **Base vision is a torch** (3 cells, through walls) until BFS and shadowcasting are learned; the first floor is a small room so a new player can see the page and the shrine.
- **Fog of war is memory**, which comes with shadowcasting: before it, you see only what is lit now.
  This makes the first floors harder to navigate, but it is the unlock the spec asks for.
- **Replays use the implementations active at the time**: player code that passes the suite but differs from the reference (Bresenham ties, for example) can give a different but still deterministic run.

### Dependencies

- `quickjs-emscripten-core` and `@jitl/quickjs-singlefile-mjs-release-sync` 0.32.0 (MIT), pinned exactly.
- Development: Bun, TypeScript, and Biome from the template.

### Interfaces

- `src/core/types.ts`: `Concept`, `Hooks`, `State`, `Puzzle`, and `CodeTrial`, the contract every concept folder implements.
- Engine inputs: `move:dx,dy`, `wait`, `descend`, `use:<slot>`, `learn:<concept>`, and `act:<action>`.
- Replay files: `{ game, version, seed, learned, inputs }`.

## Key Results and retrospective feedback
