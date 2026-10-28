# Decision Record 2026-10-23: fread Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-fread-rebuild](../../specs/SPEC-2026-09-30-fread-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-fread-rebuild.md): a private RSS and Atom reader that runs entirely in the browser, installs as a PWA, reads offline, and is published as static files on GitHub Pages.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
Private: no server, accounts, analytics, or third-party scripts; the only requests go to the feeds (and the model endpoint when summaries are on).
The parser, sanitizer, OPML, and storage modules are pure and tested.

### Nice to haves

#### Functional

Summaries of unread articles by a model picked by role, off by default.

#### Non-functional

Few runtime dependencies, and a bundle small enough to load fast on a phone.

### Avoid out of scope runaway rabbit hole risks

#### Functional

A sync server or accounts; full-text extraction of linked pages; our own HTML sanitizer.

#### Non-functional

A UI framework or a CSS build for a page with three panes and a dialog.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo, [dijonkitchen/fread](https://github.com/dijonkitchen/fread), was plain HTML, CSS, and ES modules tested with the Node test runner; the rebuild keeps plain HTML and CSS and no framework, but writes the modules in TypeScript, tested and bundled by Bun, since the template, typechecking, and the [languages decision](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) (TypeScript stays for browser code) all point there.
- **Feed and OPML parsing**: a small lenient XML parser of our own (`src/xml.ts`), not the browser's `DOMParser`, so parsing is pure and runs the same in tests and the page, and recovers from what real feeds get wrong (HTML entities, stray end tags).
  RSS 2.0, RSS 1.0 (RDF), and Atom map to one item shape in `src/feed.ts`.
- **Sanitizing**: [DOMPurify](https://github.com/cure53/DOMPurify) (audited, widely used), with a stricter policy on top in `src/sanitize.ts`: HTML profile only (no SVG or MathML), no styles, forms, frames, media, or data attributes; links only http, https, or mailto, opening in a new tab without a referrer.
  Images don't load until the reader asks, because loading one tells its host who read what; a setting turns them on.
  Tests run DOMPurify on jsdom, which DOMPurify itself tests against (happy-dom let a `javascript:` link through, so it is not used).
- **Storage**: the whole state (subscriptions, items, read flags, settings) as one JSON record in IndexedDB; every change is a pure function in `src/store.ts`.
  Each feed keeps its newest 500 items plus every unread one.
- **Offline and install**: a web app manifest and a service worker that caches the app shell with a version hash from the build; articles are read offline from IndexedDB.
  A Content Security Policy in the page allows scripts and styles only from itself.
- **Fetching**: straight from each feed's site, with no cookies or referrer; a CORS proxy is an opt-in setting with a `{url}` template, since many sites don't send CORS headers.
- **Summaries**: optional and off by default; the role list comes from [`harness/models.json`](../../../../harness/models.json) at build time, and the request goes to OpenRouter with the reader's own key (kept in the browser) and the repo's routing (zero data retention, no data collection).
  Article text is quoted as untrusted data with no tools, and the answer is shown as plain text.
- **Build and publishing**: `bun build.ts` bundles `src/app.ts` and copies `public/` into `dist/`; the root [Site workflow](../../../../.github/workflows/site.yml) builds it into the Pages site at `fread/`.

### High-level C4(context/container/component/code) diagram

```text
Feed sites (or an opt-in CORS proxy) --> fetch.ts --> feed.ts (xml.ts) --> store.ts --> IndexedDB
IndexedDB --> app.ts --> sanitize.ts (DOMPurify) --> reader pane
OPML file <--> opml.ts <--> store.ts
Service worker: app shell cache (offline)      Optional: summarize.ts --> OpenRouter (role from harness/models.json)
```

### Choices and Tradeoffs/Risks

Our own XML parser over `DOMParser`: pure and testable without a DOM, and lenient where browsers reject a whole feed for one bad entity; the risk is missing a corner of XML, covered by tests on recorded real feeds of each format.
It never produces HTML, so a parser mistake can't become an injection: all HTML goes through DOMPurify before it is shown.

DOMPurify over a hand-written sanitizer: sanitizing HTML is easy to get subtly wrong (mutation XSS), and DOMPurify is audited and maintained; the cost is one runtime dependency of about 20 KB.

One JSON record over one IndexedDB record per item: simple, atomic, and fast enough for thousands of items; if it grows slow, split items into their own store behind the same `store.ts` functions.

Images off by default trades a less pretty first read (comics feeds need one click) for the spec's privacy promise.

### Dependencies

Runtime: `dompurify`.
Development: Bun (test runner and bundler), TypeScript, Biome, and `jsdom` for sanitizer tests.

### Interfaces

- `parseFeed(xml, url) -> Feed`, `parseOpml(xml) -> Subscription[]`, `toOpml(subscriptions) -> string`, `sanitize(html, window, { base, images }) -> string`.
- `store.ts`: `State` and pure functions over it (`addFeeds`, `mergeFeed`, `markRead`, `visibleItems`, `serialize`, `deserialize`, ...).
- Proxy setting: a URL template with `{url}`, or a prefix the encoded feed URL is appended to.

## Key Results and retrospective feedback
