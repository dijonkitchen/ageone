# Adding a concept

A concept is one folder under `src/concepts/` and one line in `src/concepts/index.ts`.
The engine (`src/core/`) never changes: a test fails if it names a concept or imports one.
1. Make `src/concepts/<id>/reference.ts`: the algorithm, as plain functions.
   If it gets a code-mode trial, make each function self-contained (no imports, no outside helpers), because its source also runs in the sandbox.
2. Make `src/concepts/<id>/reference.test.ts`: unit tests of the reference.
3. Make `src/concepts/<id>/index.ts`, exporting `concept: Concept` (see `src/core/types.ts`):
   - `id`, `name`, `tier`, `requires` (ids of concepts it builds on, from its tier or lower), `unlocks` (the in-game effect, one sentence), `complexity`, and `reading` (a link to check facts against).
   - `lesson`: a few short paragraphs, and `frames(seed)`, a step-through visualization built from the reference's own trace.
   - `puzzle(seed)`: multiple-choice steps whose answers come from the reference, and how many mistakes are allowed.
     The `choice()` helper in `src/concepts/util.ts` shuffles the options and records the answer.
   - `hooks`: how it changes the game.
     It can offer a floor `generator`, `vision`, `memory`, a `scheduler`, a monster `brain`, `loot`, an `inventory` rule, page `features`, or `actions` (a key, a label, and what it does).
     For the kinds only one concept can provide, the highest `priority` wins, so a later concept can replace an earlier one.
   - `code` (optional): a code-mode trial, with the exported function names, docs, a starter, a test suite (`TestCase`s that call the player's functions), and a time budget.
     Inside hooks, call your function through `ctx.code(name, reference, valid)` so the player's code runs when they switch it on, with a fallback to the reference.
   - `sandbox` (optional): frames of the algorithm running on any floor.
4. Add the concept to `CONCEPTS` in `src/concepts/index.ts`, in codex order.
5. Run `make check`.
   `src/concepts/concepts.test.ts` checks the new folder against the contract: codex entry, lesson, puzzles for 40 seeds, a hook, and for code mode, that the reference passes its suite directly and inside the sandbox.
