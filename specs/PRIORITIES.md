# Priorities

updated_at: 2026-09-30

Table of specs, listing their number, dependency (if any), priority, description, difficulty, and status.
Priority 1 is the highest.
Rows are sorted by priority (highest first), then by difficulty (easiest first).
Status is one of `Open`, `In progress (<owner>)`, `Blocked (<reason>)`, or `Done`.

Whenever a spec is added or updated, re-evaluate every row's priority, then update `updated_at`.

Every project spec (in a `projects/<slug>/specs/` folder) also needs [SPEC-0005](SPEC-0005-projects-scaffold.md), whatever its dependency column says ([Projects in ageone](../docs/decisions/2026-09-30-projects-in-ageone.md)).

| Number | Dependency | Priority | Description | Difficulty | Status |
|--------|------------|----------|-------------|------------|--------|
| [SPEC-0003](SPEC-0003-make-setup.md) | None | 1 | Make setup: one idempotent `make` installs Nix and devenv, builds the pinned environment (Node.js LTS for pi), and checks it | Low | Done |
| [SPEC-0005](SPEC-0005-projects-scaffold.md) | None | 2 | Projects scaffold: `projects/`, per-project specs and decision records, Bun and uv in devenv, a project template, and CI per changed project | Low | Open |
| [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) | SPEC-0001 | 2 | Vendor-neutral AI harness: pi + model roles config + web search + private open-weight models + evals on our own tasks, with a runner that swaps harnesses or calls models directly | Medium | Open |
| [SPEC-0016](SPEC-0016-prompt-injection-skill.md) | SPEC-0005 | 3 | Prompt injection skill: shared CaMeL-style skill and library for projects that feed untrusted text to models, restarted from the skills repo | Low | Open |
| [SPEC-0004](SPEC-0004-eval-benchmark-pages.md) | SPEC-0002 | 3 | Eval and benchmark pages: static site of our experiments comparing ways to do things (output formats like TOON vs CSV vs JSON, tool interfaces, harnesses) across models | Medium | Open |
| [SPEC-0006](../projects/connect6/specs/SPEC-0006-connect6-rebuild.md) | SPEC-0005 | 4 | Connect6 rebuild: pure engine, web UI, MCTS and LLM players, and a tournament feeding the eval pages | Medium | Open |
| [SPEC-0007](../projects/og-trail/specs/SPEC-0007-og-trail-rebuild.md) | SPEC-0005 | 4 | OG Trail rebuild: modern-life Oregon Trail engine, terminal and browser frontends, and agent players feeding the eval pages | Medium | Open |
| [SPEC-0008](../projects/simplefit/specs/SPEC-0008-simplefit-rebuild.md) | SPEC-0005 | 5 | SimpleFit rebuild: offline-first longevity fitness PWA on GitHub Pages, with tested formulas and backups | Low | Open |
| [SPEC-0013](../projects/fread/specs/SPEC-0013-fread-rebuild.md) | SPEC-0005 | 5 | fread rebuild: private client-side RSS and Atom reader PWA with OPML and optional LLM summaries | Low | Open |
| [SPEC-0009](../projects/fite/specs/SPEC-0009-fite-rebuild.md) | SPEC-0005 | 5 | Fite rebuild: procedural pixel-art tournament fighter with CPU levels and keyboard, touch, and gamepad controls | Low | Open |
| [SPEC-0015](../projects/posse-bliki/specs/SPEC-0015-posse-bliki-rebuild.md) | SPEC-0005 | 5 | POSSE bliki rebuild: Obsidian-written blog and wiki built to an IndieWeb static site on GitHub Pages | Low | Open |
| [SPEC-0014](../projects/sonal/specs/SPEC-0014-sonal-rebuild.md) | SPEC-0002 | 6 | Sonal rebuild: LLM sentiment and themes of a YouTube video's comments, with a cited summary | Low | Open |
| [SPEC-0011](../projects/needle/specs/SPEC-0011-needle-walking-skeleton.md) | SPEC-0002 | 6 | Needle: local-first browser research assistant saving cited answers as Obsidian Markdown, milestones M1 and M2 | Medium | Open |
| [SPEC-0012](../projects/roi/specs/SPEC-0012-roi-rebuild.md) | SPEC-0005 | 6 | ROI rebuild: offline stock and options screening and backtesting core, plus a cited LLM research assistant | Medium | Open |
| [SPEC-0010](../projects/aiprofile/specs/SPEC-0010-aiprofile-mvp.md) | SPEC-0002 | 7 | AI profile platform MVP: GitHub sign-in, evidence ingest, cited profile patches the worker accepts | High | Open |
| [SPEC-0017](../projects/llm-from-scratch/specs/SPEC-0017-llm-from-scratch.md) | SPEC-0005 | 8 | LLM from scratch: tokenizer, small transformer, and training loop on a laptop, compared with a tiny open-weight model | Medium | Open |
| [SPEC-0001](SPEC-0001-agent-todo-repo.md) | None | 9 | Agent todo repo: monorepo foundation of specs, decisions, and priorities | Low | Done |
