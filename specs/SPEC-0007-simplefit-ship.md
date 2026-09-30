# SPEC-0007: SimpleFit Ship

## Repo

[dijonkitchen/simplefit](https://github.com/dijonkitchen/simplefit), an offline-first PWA for longevity training, with no server, build step, or dependencies.
See [Project Repos](../docs/decisions/2026-09-30-project-repos.md).

## Functional requirements

Get SimpleFit from one initial commit to an app JC uses daily on a phone.

- CI runs `npm test` on every pull request.
- The app is published to GitHub Pages over HTTPS from `main`, so it installs to a home screen and works offline.
- The service worker updates cleanly: a new version is picked up on the next launch and never serves a mix of old and new files.
- A reminder in the app when Export was last run more than 30 days ago, since `localStorage` is the only copy of the data.
- An `AGENTS.md` (with `CLAUDE.md` symlinked to it) describing commands and conventions, as other project repos have.

## Non-functional requirements

- Private: data stays on the device; no analytics or network calls beyond loading the app.
- Simple: no build step and no dependencies are added.
- The formulas in `fitness.js` stay covered by tests, with sources cited as today.

## Definition of done

1. CI passes on `main`, and the Pages URL installs and works in airplane mode on iOS and Android.
2. Shipping a new version updates an installed app on its next launch.
3. The backup reminder appears and clears after an Export.
