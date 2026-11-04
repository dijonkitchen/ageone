# Decision Record 2026-10-23: Needle Stack

## Status timeline

2026-10-23: Proposed by Claude

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the walking skeleton spec](../../specs/SPEC-2026-09-30-needle-walking-skeleton.md): a pure-browser PWA that keeps Markdown notes in the browser's private file system, with end-to-end tests of each milestone outcome.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
No server, no accounts, no runtime dependencies to ship.

### Nice to haves

#### Functional

Modules that run under plain `bun test`, so most behavior is tested without a browser.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A UI framework, a bundler config, or a Workbox build for an app with one page and a 30-line service worker.

#### Non-functional

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).

The old repo planned TypeScript, Bun, Lit, Workbox, Playwright, and Biome.
Still holding: TypeScript, Bun, Biome, and Playwright.
Changed: no Lit and no Workbox.
The page is one form, one list, and a settings panel, so plain DOM code written with `textContent` is smaller and needs no framework; the hand-written service worker is the same one-file pattern the fread project uses.
- Code is in `src/`, with the browser-only parts (`app.ts`, the OPFS vault) kept thin and everything else testable under `bun test src`.
- `bun build.ts` bundles `src/app.ts` and `public/` into `dist/`, stamping the service worker's cache version.
- End-to-end tests (`e2e/`, `make e2e`) use `playwright-core` against `dist/` in Chromium.
  Bun cannot drive Playwright's pipe transport, so `e2e/serve.ts` starts Chromium itself and connects over CDP.
  `make check` stays browser-free; the Projects workflow runs `make e2e` for needle after installing Chromium.
- Models are chosen by role from `harness/models.json`, imported at build time, so a model change is a config change.
  The extra `private` role picks the first open-weight model and pins OpenRouter to the allowlisted hosts with zero data retention.
- Search results and snippets are untrusted: `src/untrusted.ts` strips control characters, flags instruction-like text, and fences each source in `<untrusted>` tags, following the policy of `skills/prompt-injection-prevention`.
  That skill's library is Python and not yet on `main`, so the browser port is a small local copy of the policy; replace it with a shared port if one appears.
- The vault is the database.
  The search index lives in `.needle/index.json` as a cache, is rebuilt from the notes when missing or damaged, and is serialized with sorted keys so a rebuild is byte-identical.
- The browser holds the OpenRouter key and settings in `localStorage`, which stays on the device; Kagi is reached only through a proxy the user runs, since Kagi's API sends no CORS headers and its key must not ship in a page.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Plain DOM over Lit: less to learn and ship, at the cost of hand-written rendering if the UI grows (M3 and M4 may revisit this).

The OpenRouter key sits in `localStorage` where any script on the origin could read it; the app loads no third-party scripts, and the key is the user's own.

### Dependencies

[SPEC-2026-09-26-vendor-neutral-ai-harness](../../../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md) for the model roles config.

### Interfaces

Notes are `research/<id>.md` files in the `research/v1` format: frontmatter (`schema`, `id`, `question`, `created`, `model`, `sources`), a `#` heading with the question, the answer with `[^n]` markers, and one footnote per source.

## Key Results and retrospective feedback
