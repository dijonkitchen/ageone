# SPEC-2026-09-30-simplefit-rebuild: SimpleFit Rebuild

Restarts [dijonkitchen/simplefit](https://github.com/dijonkitchen/simplefit) in this folder, `projects/simplefit/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/simplefit/docs/decisions/`.

A deliberately small, offline-first fitness app for health and longevity that tracks only the best-evidenced metrics and says what to do next.

## Functional requirements

- Weekly targets and logging: Zone 2 minutes, Zone 4 interval minutes, strength sessions, resting heart rate, and VO₂max.
- The old repo's formulas as pure, tested functions with their sources: max heart rate (Tanaka), Karvonen zones, VO₂max estimate (Uth) overridable by a measured value, and fitness bands by age and sex.
- A "next action" for the week and trends showing whether each metric improves.
- An installable PWA that works offline, published to GitHub Pages; new versions load on the next launch without mixing old and new files.
- Export and import of all data, and a reminder when the last export is more than 30 days old.

## Non-functional requirements

- Private: data stays on the device; no accounts, analytics, or network calls beyond loading the app.
- Simple: no server; a build step only if the stack decision justifies it.
- Readable at phone width, in light and dark themes.

## Definition of done

1. The first decision record in `projects/simplefit/docs/decisions/` chooses the stack (old: vanilla JavaScript PWA, no build or dependencies, Node test runner).
2. `projects/simplefit/` is set up by `make`, and its CI job passes on `main`.
3. Every formula is covered by tests citing its source.
4. The Pages URL installs on iOS and Android and works in airplane mode, and a new version updates an installed app on its next launch.
5. Export then import on another device restores all data, and the backup reminder clears after an export.
