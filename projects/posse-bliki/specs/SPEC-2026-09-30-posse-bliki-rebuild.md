# SPEC-2026-09-30-posse-bliki-rebuild: POSSE Bliki Rebuild

Restarts [dijonkitchen/posse-bliki](https://github.com/dijonkitchen/posse-bliki) in this folder, `projects/posse-bliki/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/posse-bliki/docs/decisions/`.

A personal blog and wiki written in Obsidian as plain Markdown, built into a static site on GitHub Pages, following POSSE and IndieWeb standards.

## Functional requirements

- Content is an Obsidian vault of Markdown with `[[wiki links]]`, tags, and frontmatter, validated against a content schema; no Obsidian plugins required.
- The build turns it into HTML with microformats2 (`h-entry`, `h-card`, `h-feed`), RSS 2.0 and JSON Feed 1.1, a sitemap, `robots.txt`, a 404 page, tag pages, a notes index, and alias redirects.
- The old repo's specs (output contract, URL policy, feeds, IndieWeb, build invariants) become this spec's acceptance criteria, enforced by a test harness, with the build itself replaceable.
- Webmention sending for new posts, and POSSE copies to other sites linking back to the original.
- Fits the [Obsidian and LLM Wiki](../../../docs/decisions/2026-09-28-obsidian-and-llm-wiki.md) decision.

## Non-functional requirements

- Simple: a small build script, no vendored static site generator.
- Stable URLs: published URLs never change without a redirect.
- `make serve` rebuilds on save for local preview.

## Definition of done

1. The first decision record in `projects/posse-bliki/docs/decisions/` chooses the stack (old: Python, uv, a small custom build, spec plus harness).
2. `projects/posse-bliki/` is set up by `make`, and its CI job passes on `main`.
3. The harness passes on the migrated content, and feeds validate with standard validators.
4. Pushing to `main` deploys the site to GitHub Pages.
5. A post's microformats parse correctly with an IndieWeb parser, and a Webmention is sent for a new post.
