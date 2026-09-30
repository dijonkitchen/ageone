# SPEC-0009: Fite Rebuild

Restarts [dijonkitchen/Fite](https://github.com/dijonkitchen/Fite) in `projects/fite/`, per [Projects in ageone](../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `docs/decisions/fite/`.

"Shell Shock", a browser tournament fighter with four turtle ninjas and a boss, drawn as procedural pixel art with synthesized sound and no asset files.

## Functional requirements

- 1P tournament (random bracket, then the boss) and 2P local versus; best of three rounds, 60-second timer.
- Movement, jumping, crouching, blocking by holding away, punch, kick, and a meter-gated ranged special, with per-fighter frame data.
- Procedural sprites and stages from one shared rig, and Web Audio sound effects.
- A CPU player that sends the same inputs a person would, with easy, normal, and hard levels that change reaction time and blocking, not damage.
- Keyboard, touch, and gamepad controls.
- Published to GitHub Pages.

## Non-functional requirements

- No asset files, and no copyrighted characters, names, or assets.
- Holds 60 frames per second on a mid-range phone.
- A headless harness runs thousands of frames of CPU-versus-CPU combat in CI with no browser.

## Definition of done

1. The first decision record in `docs/decisions/fite/` chooses the stack (old: plain JavaScript scripts on a canvas, no build, runs from `file://`).
2. `projects/fite/` is set up by `make`, and its CI job passes on `main`.
3. The headless harness passes in CI, and a sprite sheet regenerated from the sprite code matches the committed one.
4. The hard CPU beats the easy CPU in most of 50 simulated matches.
5. A full tournament is playable on the Pages URL with keyboard, touch, and a gamepad.
