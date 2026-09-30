# SPEC-0008: Fite Ship

## Repo

[dijonkitchen/Fite](https://github.com/dijonkitchen/Fite), "Shell Shock", a browser tournament fighter with procedural pixel art and no build step or dependencies.
See [Project Repos](../docs/decisions/2026-09-30-project-repos.md).

## Functional requirements

Make the game playable by anyone from a link, and the CPU worth fighting.

- CI runs `node test/harness.js` on every pull request, and fails when `node test/render.js` would change `test/spritesheet.png`.
- The game is published to GitHub Pages from `main`.
- CPU difficulty levels (easy, normal, hard), chosen in the menu, changing reaction time and blocking, not damage.
- Touch controls on phones and tablets, and gamepad support through the Gamepad API.
- An `AGENTS.md` (with `CLAUDE.md` symlinked to it) describing commands and conventions.

## Non-functional requirements

- Keeps no build step, no dependencies, and no asset files; it still runs from `file://`.
- Holds 60 frames per second on a mid-range phone.
- Ships no copyrighted characters, names, or assets.

## Definition of done

1. CI passes on `main`, and the Pages URL plays on desktop and phone.
2. The headless harness runs each difficulty, and the hard CPU beats the easy CPU in most of 50 simulated matches.
3. A match is playable end to end with touch controls and with a gamepad.
