# Decision Record 2026-10-23: simplefit Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-simplefit-rebuild](../../specs/SPEC-2026-09-30-simplefit-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-simplefit-rebuild.md): weekly targets and logs for Zone 2, Zone 4 intervals, strength, resting heart rate, and VO₂max; the formulas as tested functions with sources; a next action and trends; export, import, and a backup reminder; an installable offline PWA on GitHub Pages that updates cleanly.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
Private (no accounts, analytics, or network calls beyond loading the app), no server, readable at phone width in light and dark themes.

### Nice to haves

#### Functional

Heart rate zones shown in beats per minute; a fitness band for VO₂max by age and sex.

#### Non-functional

No runtime dependencies; a page that loads instantly from the cache.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Wearable or health-app sync, workout plans, charts beyond a sparkline per metric.

#### Non-functional

A UI framework, a database, or sync between devices (export and import cover moving data).

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo, [dijonkitchen/simplefit](https://github.com/dijonkitchen/simplefit), was a vanilla JavaScript PWA with no build or dependencies, tested with the Node test runner.
The rebuild keeps plain HTML, CSS, and no runtime dependencies, but writes the code in TypeScript, so it needs a build step: Bun bundles it, runs the tests, and stamps the service worker.
The spec allows a build step if justified: typechecked formulas and data validation, the template, and the [languages decision](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) (TypeScript for browser code) justify one small build that also fingerprints each release.
- **Formulas** (`src/formulas.ts`): pure functions, each with its citation in the code and a test using the source's numbers. DOIs were checked against Crossref.
  - Max heart rate is 208 − 0.7 × age (Tanaka 2001), unless a measured max is set.
  - Zones are percentages of heart rate reserve (Karvonen 1957), using the usual 10-point bands. Zone 2 is 60–70% and Zone 4 is 80–90%.
  - VO₂max is estimated as 15.3 × HRmax ÷ HRrest (Uth 2004), unless a measured value is logged.
  - Fitness bands come from the FRIEND 2022 treadmill percentiles by sex and age decade (Kaminsky 2022).
  - The default targets are 150 Zone 2 minutes and 2 strength sessions a week, from the WHO 2020 guidelines, and 16 Zone 4 minutes (one 4 × 4 session, Helgerud 2007).
- **Data** (`src/store.ts`): one JSON record in `localStorage`, with every change a pure function.
  Data that fails validation on load is set aside under another key, never overwritten.
  The app asks the browser to make storage persistent.
- **Advice** (`src/advice.ts`): weeks start on Monday.
  - The next action goes in order: profile, then a resting heart rate if none in 7 days, then the interval session, then strength, then the Zone 2 minutes per remaining day, then rest.
  - Trends compare the first and second halves of the last 8 weeks, counting finished weeks only for totals. A lower resting heart rate counts as better.
- **Backup**: export downloads the whole record as JSON and stamps the export time. Import validates the file and replaces the data after confirming. A reminder shows when there is data and no export in 30 days.
- **Offline and updates** (`public/sw.js`, `build.ts`):
  - The build hashes every file into the service worker's cache name.
  - The worker caches all files of its version together and serves only from its own cache, so one launch never mixes versions.
  - A new version installs in the background and waits. At the next launch, the page activates it before use and reloads once.
- **Install**: a manifest with an SVG icon, plus 180 and 512 pixel PNG icons that the build draws (iOS uses the PNG apple-touch-icon).
- **Publishing**: `bun build.ts` writes `dist/`. The root [Site workflow](../../../../.github/workflows/site.yml) builds it into the Pages site at `simplefit/`.

### High-level C4(context/container/component/code) diagram

```text
index.html + app.ts --> advice.ts --> formulas.ts
        |                   |
        +--> store.ts <-----+        localStorage (one JSON record)
        |
        +--> export/import JSON file        sw.js: one cache per build, activated at the next launch
```

### Choices and Tradeoffs/Risks

`localStorage` over IndexedDB: the data is a few hundred small records, and synchronous reads keep the code simple. Safari may clear storage for sites not added to the home screen after weeks without use. The installed app, the persistence request, and the 30-day backup reminder cover that risk.

Activating updates at launch over `skipWaiting` on install: a running app never swaps files under itself, and the cost is one quick reload at launch when an update is waiting.

The FRIEND table is from the 2022 paper's treadmill standards. The 20–29 medians were checked against the paper's abstract and table snippet, and the rest came from a published transcription, so the test pins the medians and checks the table's ordering.

### Dependencies

None at runtime.
Development: Bun (test runner and bundler), TypeScript, and Biome.

### Interfaces

- Backup file: `{ version: 1, profile: { birthYear, sex, maxHr }, targets: { zone2, zone4, strength }, entries: [{ id, day: "YYYY-MM-DD", kind, value }], lastExport }`, with `kind` one of `zone2`, `zone4`, `strength`, `rhr`, or `vo2max`.
- `nextAction(data, day)`, `trends(data, day)`, `week(data, day)`, `heart(data, day)`, `vo2max(data, day)`, `backupDue(data, now)`.

## Key Results and retrospective feedback
