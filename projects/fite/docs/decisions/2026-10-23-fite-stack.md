# Decision Record 2026-10-23: fite Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-fite-rebuild](../../specs/SPEC-2026-09-30-fite-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-fite-rebuild.md): "Shell Shock", a browser tournament fighter with four turtle ninjas and a boss, procedural pixel art and sound, a CPU at three levels, and keyboard, touch, and gamepad controls, published on GitHub Pages.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
No asset files and nothing copyrighted; 60 frames per second on a mid-range phone; a headless harness that runs CPU-versus-CPU matches in CI with no browser.

### Nice to haves

#### Functional

Hit sparks, screen shake, and a select screen that shows each fighter's style.

#### Non-functional

A small bundle and instant start, so a phone on a slow connection can play within a second or two.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Combos, throws, online play, more fighters, or story; the spec asks for one tournament done well.

#### Non-functional

A game engine or physics library; an image editor pipeline; music.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo, [dijonkitchen/Fite](https://github.com/dijonkitchen/Fite), was plain JavaScript scripts on a canvas with no build, run from `file://`.
That no longer holds: the spec needs a headless harness and tests in CI, which want modules, and the [languages decision](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) keeps TypeScript for browser code, so the rebuild is TypeScript modules tested and bundled by Bun into one script, still with no runtime dependencies and still a canvas.

- **Simulation** (`src/sim.ts`): a pure, deterministic, fixed-step model of two fighters, projectiles, and a best-of-three match with a 60-second clock.
  Inputs are bitmasks of held buttons, so people, the CPU, and tests all drive it the same way, and the same inputs always give the same match.
  Per-fighter frame data (startup, active, recovery, damage, stun, reach) comes from one base move set tuned per fighter in `src/fighters.ts`.
  Lows must be blocked crouching and jump-ins standing; mids either way; specials need half the meter and chip through a block.
- **CPU** (`src/cpu.ts`): returns the same input bitmask a pad would, and sees the opponent only as they were some frames ago.
  Levels change only that reaction time and how often it blocks, guards, anti-airs, attacks, and throws specials; never damage or speed.
- **Art** (`src/sprites.ts`, `src/stage.ts`, `src/pixels.ts`): every fighter is one rig (hips, torso, head, two-joint limbs) posed by a few angles per pose and drawn with a handful of pixel primitives into a plain RGBA buffer, then outlined.
  Fighters differ by colour, and the boss adds ridges and a beak.
  Stages use the same primitives with a seeded generator.
  `bun run sheet` writes the whole sheet to `sprites/sheet.png`, and a test fails if the code no longer draws exactly that image, so art changes are reviewed as images.
- **Text** (`src/font.ts`): a 3x5 pixel font defined in code, so there are no font files.
- **Sound** (`src/audio.ts`): Web Audio oscillator sweeps and filtered noise, started on the first input as browsers require.
- **Controls** (`src/controls.ts`): keyboard (WASD/FGH for player 1, arrows/KL; for player 2), standard-mapping gamepads (d-pad or stick, A punch, B kick, Y special, Start), and an on-screen stick and buttons shown after the first touch.
- **Loop and drawing** (`src/app.ts`, `src/render.ts`): 60 simulation steps per second whatever the display rate, drawn to a 320x180 canvas scaled up with crisp pixels; sprites and stages are drawn once into offscreen canvases and copied each frame.
- **Harness** (`src/headless.ts`, `harness.ts`): runs CPU-versus-CPU matches and checks invariants (finite numbers, inside the walls, health and meter in range) every frame; the tests run every pairing and 50 hard-versus-easy matches.
- **Publishing**: `bun build.ts` bundles `src/app.ts` and copies `public/` into `dist/`; the root [Site workflow](../../../../.github/workflows/site.yml) builds it into the Pages site at `fite/`.

### High-level C4(context/container/component/code) diagram

```text
keyboard / gamepad / touch --> controls.ts --+
                                             +--> game.ts (screens, bracket) --> sim.ts (one frame) --> events --> audio.ts
                              cpu.ts --------+                                        |
                                                                                      v
                       sprites.ts + stage.ts (pixels.ts) --> render.ts --> 320x180 canvas
headless.ts + harness.ts: cpu.ts x2 --> sim.ts, invariants checked each frame (CI)
```

### Choices and Tradeoffs/Risks

A pure simulation over one that reads the clock or the DOM: it makes the harness, replays, and tests possible; the cost is that the page has to feed it fixed steps, which `app.ts` does with an accumulator.

Code-drawn sprites over a hand-drawn sheet: the spec bans asset files, and a rig means every new pose works for every fighter at once; the cost is simpler-looking art than hand pixelling.

A committed sheet compared in CI over no snapshot: an accidental art change fails loudly; a deliberate one is one `bun run sheet` and shows in review as an image diff.
The comparison decodes the PNG and compares pixels, so a different zlib can't fail it.

The CPU sees a delayed copy of the opponent rather than predicting from inputs: reaction time is then a real, testable knob, and the CPU can't read inputs a person couldn't see.

Measured with Chromium at 4x CPU throttling, frames hold 16.7 ms (60 per second); a real mid-range phone still needs checking on the Pages URL.

### Dependencies

None at runtime.
Development: Bun (test runner and bundler), TypeScript, and Biome.

### Interfaces

- `step(match, [input1, input2])` advances one frame; `newMatch(def1, def2)`; inputs are `UP | DOWN | LEFT | RIGHT | PUNCH | KICK | SPECIAL | START` bitmasks.
- `new Cpu(level, seed).input(match, side)` returns that frame's input.
- `simulate(player1, player2, seed)` plays a whole CPU match headless; `bun harness.ts 50 hard easy` prints win rates.
- `tick(game, [input1, input2])` runs the screens around the fight.

## Key Results and retrospective feedback
