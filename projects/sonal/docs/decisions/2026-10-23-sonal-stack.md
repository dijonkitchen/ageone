# Decision Record 2026-10-23: sonal Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-sonal-rebuild](../../specs/SPEC-2026-09-30-sonal-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-sonal-rebuild.md) that fetches a YouTube video's top-level comments behind a source interface, classifies sentiment and themes with a role-chosen LLM, and serves a page with the split, themes, and a cited summary, cached per video.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
No network in tests; API keys only from the environment.

### Nice to haves

#### Functional

Another platform is one new `CommentSource`.

#### Non-functional

Cheap: batched classification on the `cheap` role.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Accounts, replies to comments, history across videos, a database.

#### Non-functional

A web framework or front-end bundler for one server-rendered page.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo's stack (Ruby on Rails, Hotwire, Faraday, the `yt` gem, a word-list scorer) does not hold: the work is now one HTTP API plus model calls plus one page, which TypeScript on Bun covers with `fetch` and `Bun.serve` and no runtime dependencies, and it matches the repo's other model-calling projects.
The word list survives only as `src/baseline.ts`, the bar the classifier must beat.
- **Sources**: `CommentSource` (`parse`, `fetchVideo`, `fetchComments`); `src/youtube.ts` uses the YouTube Data API `videos` and `commentThreads` endpoints with `YOUTUBE_API_KEY`.
- **Model**: `src/model.ts` reads the role's model from the root [`harness/models.json`](../../../../harness/models.json) and calls OpenRouter with its routing settings; classification and the summary use `cheap` unless `SONAL_ROLE` says otherwise.
- **Untrusted comments**: the model call is quarantined (`src/quarantine.ts`). It has no tools, sees comments only as JSON string values, and its reply is accepted only if it validates: known comment IDs, enum sentiments, short `[a-z0-9 ]` theme labels, and summary sentences whose citations all exist, with links stripped. Everything is HTML-escaped on the page.
  The shared [prompt injection skill](../../../../specs/SPEC-2026-09-30-prompt-injection-skill.md) is not on `main` yet, so this applies its approach by hand (data stays out of control flow; output is structured and checked) and should switch to the library when it lands.
  This does not stop a comment from skewing the labels it is given; it limits the damage to a wrong label.
- **Cache**: one JSON file per video in `.cache/`, so a repeat visit neither refetches nor reclassifies.

### High-level C4(context/container/component/code) diagram

```text
browser ─> Bun.serve (src/cli.ts) ─> analyzeUrl (src/service.ts) ─> cache (.cache/<video>.json)
                                          ├─> CommentSource (src/youtube.ts) ─> YouTube Data API
                                          └─> classify + summarize (src/analyze.ts) ─> quarantined Chat (src/model.ts) ─> OpenRouter
```

### Choices and Tradeoffs/Risks

- Up to 200 top-level comments by relevance, 25 per batch, each truncated to 600 characters: cheap and enough for a reaction, but not a census of a viral video.
- A comment the model skips or garbles is left unclassified and counted out of the split, not guessed.
- One retry on a malformed reply, then the request fails with the reason.

### Dependencies

None at runtime; Biome, TypeScript, and `@types/bun` for development.

### Interfaces

- `bun run src/cli.ts <url>` prints the analysis JSON; `bun run src/cli.ts --serve [port]` serves the page.
- `bun run src/eval.ts [role ...] [--append]` measures classifier accuracy on `src/fixtures/labeled.json` against the word list.
- Environment: `YOUTUBE_API_KEY`, `OPENROUTER_API_KEY`, optional `SONAL_ROLE`, `SONAL_CACHE`, `SONAL_MODELS`.

## Key Results and retrospective feedback
