# SPEC-2026-09-30-fread-rebuild: fread Rebuild

Restarts [dijonkitchen/fread](https://github.com/dijonkitchen/fread) in this folder, `projects/fread/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/fread/docs/decisions/`.

A private, fully client-side RSS and Atom reader, installable as a PWA, with no accounts, server, or tracking.

## Functional requirements

- Subscribe by URL to RSS 2.0, RSS 1.0 (RDF), and Atom feeds; import and export OPML.
- Read view with feed HTML sanitized of scripts, event handlers, and dangerous URLs.
- Unread tracking with per-feed counts and an unread-only filter; light, dark, and auto themes.
- Fetches feeds directly, with an optional user-chosen CORS proxy (off by default).
- Works offline as an installable PWA, published to GitHub Pages.
- Optional, off by default: summaries of unread articles by an LLM picked by role through the model roles config from SPEC-2026-09-26-vendor-neutral-ai-harness, with article text treated as untrusted.

## Non-functional requirements

- Private: the only network requests are the feeds themselves (and the model endpoint, if summaries are turned on); no analytics or third-party scripts.
- The parser, sanitizer, OPML, and storage modules are pure and tested.

## Definition of done

1. The first decision record in `projects/fread/docs/decisions/` chooses the stack (old: plain HTML, CSS, and ES modules, Node test runner).
2. `projects/fread/` is set up by `make`, and its CI job passes on `main`.
3. The parser handles real samples of each feed format, and the sanitizer blocks a set of known attack payloads, shown by tests.
4. OPML round-trips subscriptions with another reader.
5. The Pages URL installs and reads cached articles offline.
