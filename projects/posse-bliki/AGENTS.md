# posse-bliki

A personal blog and wiki written in Obsidian as plain Markdown and built into an IndieWeb static site, for its author to publish first and copy elsewhere (POSSE).
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-posse-bliki-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-posse-bliki-stack.md): Python, uv, a small custom build, and the harness.
- [README](README.md): the vault layout, front matter schema, URL policy, and how to publish.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests (the harness); CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `make serve`: preview at http://localhost:8000, rebuilding on save.
- `make build`: write `_site/` and record new URLs in `urls.lock`.

## Rules

- Commit the lockfile (`uv.lock`) with any dependency change.
- Content is plain Markdown: relative or `[[wiki]]` links only, no Obsidian plugins.
- Published URLs never change without an alias; commit `urls.lock` changes with the page that adds them (`make build`), and never delete lines from it.
- Keep the build small: no static site generator; add a dependency only for what the standard library lacks.
