# Decision Record 2026-10-23: posse-bliki Stack

## Status timeline

2026-10-23: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-posse-bliki-rebuild.md): Markdown with wiki links to HTML with microformats2, two feeds, a sitemap and redirects, plus Webmention sending, all checked by a test harness.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
A small build script with no vendored static site generator, and stable URLs.

### Nice to haves

#### Functional

Backlinks on notes, and a live-reloading local preview.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Themes, a template language, comments, search, and an image pipeline.
Receiving Webmentions: a hosted endpoint such as webmention.io does it.

#### Non-functional

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo ([dijonkitchen/posse-bliki](https://github.com/dijonkitchen/posse-bliki)) used Python, uv, a small custom build, and a spec plus harness.
That stack still holds: the restart keeps it and moves the old specs' acceptance criteria into the test harness.

### High-level C4(context/container/component/code) diagram

```text
content/ (Obsidian vault) + site.toml
  -> content.py  parse and validate front matter, URL policy
  -> render.py   [[wiki links]] and backlinks, Markdown, h-entry/h-feed/h-card templates
  -> feeds.py    RSS 2.0, JSON Feed 1.1, sitemap, robots
  -> build.py    write _site/, alias redirects, urls.lock check
webmention.py    discover endpoints and send, after the deploy
```

### Choices and Tradeoffs/Risks

- Python 3.12 with uv, `markdown-it-py` (CommonMark) and `PyYAML` as the only runtime dependencies; HTML is built with plain string templates, which stays readable at this size.
- Raw HTML in Markdown is off, so a post cannot inject markup; the cost is no inline HTML in content.
- Stable URLs are enforced by `urls.lock`: the build fails if a recorded URL stops resolving, and an alias is the fix.
- The site deploys under `/bliki/` of the repository's one GitHub Pages site, shared with the eval pages ([site workflow](../../../../.github/workflows/site.yml)). Links carry the path prefix from `site.url`; a custom domain later only changes `site.toml`.
- Webmentions are sent statelessly for posts of the last seven days after each deploy, since receivers deduplicate; this avoids a state file but repeats requests.
- Feeds are checked with feedparser and structural JSON Feed rules in tests rather than hosted validators, which need network.

### Dependencies

Runtime: markdown-it-py, PyYAML.
Tests only: pytest, mf2py (an IndieWeb microformats parser), feedparser, mypy, ruff.

### Interfaces

`bliki build | check | serve | webmention`; see the [README](../../README.md).

## Key Results and retrospective feedback
