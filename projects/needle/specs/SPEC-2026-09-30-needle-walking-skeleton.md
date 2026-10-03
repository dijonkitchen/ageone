# SPEC-2026-09-30-needle-walking-skeleton: Needle Walking Skeleton and Integrations

Restarts [dijonkitchen/needle](https://github.com/dijonkitchen/needle) in this folder, `projects/needle/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/needle/docs/decisions/`.

A local-first, pure-browser research assistant: ask a question, it searches the web, synthesizes a cited answer with an LLM, and saves everything as plain Markdown you can open in Obsidian.

## Functional requirements

- The old repo's spec corpus (spec, architecture, domain model, roadmap) is rewritten here as this spec's sources, keeping its milestone outcomes.
- M1, walking skeleton with fake providers: ask, get a cited answer, save a `research/v1` Markdown note with frontmatter to the browser's private file system, list and open notes after reload, install as an offline PWA.
- M2, real integrations: the answering model is picked by role through the model roles config from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md), never a model ID in code, including the private open-weight models that config provides; Kagi search through a user-supplied proxy, or paste-in results with no proxy; mirroring the vault to a chosen folder, or zip export where the browser can't; full-text search over the library.
- Fetched web pages are untrusted and handled with [`skills/prompt-injection-prevention`](../../../specs/SPEC-2026-09-30-prompt-injection-skill.md).

The preference profile (M3) and history-aware reasoning (M4) are later specs.

## Non-functional requirements

- Local-first: no accounts or server; the Markdown vault is the database, and any index is rebuilt from it.
- Human-auditable: notes render correctly in Obsidian, with frontmatter as properties and working footnotes.
- End-to-end browser tests describe each milestone outcome before its code.

## Definition of done

1. The first decision record in `projects/needle/docs/decisions/` chooses the stack (old plan: TypeScript, Bun, Lit, Workbox, Playwright, Biome).
2. `projects/needle/` is set up by `make`, and its CI job passes on `main`.
3. All M1 and M2 outcomes pass as end-to-end tests in CI.
4. A generated note opens correctly in Obsidian (checked once by hand).
5. Deleting the search index and rebuilding it from the vault gives identical results.
