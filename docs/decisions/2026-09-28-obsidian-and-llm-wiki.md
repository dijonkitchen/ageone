# Decision Record 2026-09-28: Obsidian and the LLM Wiki Pattern

## Status timeline

2026-09-28: Proposed by Claude, at JC's request

2026-09-28: Accepted by JC

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Decide whether the repo adopts the "LLM wiki" pattern with Obsidian, or keeps its current layout of specs, decision records, and priorities.

The LLM wiki pattern (popularized by Andrej Karpathy, often used with Obsidian) has three layers:

1. Raw sources: immutable inputs such as articles, papers, and transcripts.
2. The wiki: Markdown pages the LLM writes and maintains from those sources, with an index page and an append-only log.
3. A schema: a file like `CLAUDE.md` telling the agent how to ingest sources, answer queries, and lint the wiki.

#### Non-functional

Keeps the [Conventions](2026-09-26-conventions.md): works with any agent or harness, not only one tool, and links render on GitHub.

### Nice to haves

#### Functional

Graph view, backlinks, and search for people browsing the repo.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Rewriting existing files into Obsidian-specific syntax.
Building a knowledge layer before a spec needs one.

#### Non-functional

## Decision

Keep the current layout and conventions.
Obsidian is an optional viewer, not a dependency.

The repo already follows the LLM wiki pattern for specs and decisions:

| LLM wiki piece | This repo |
|---|---|
| Schema | `README.md` (with `AGENTS.md` and `CLAUDE.md` symlinked to it) |
| Index | `specs/PRIORITIES.md` |
| Pages maintained by the LLM | `specs/`, `docs/decisions/` |
| Log | Git history and each decision record's status timeline |
| Raw sources | None yet |

### Rules

1. Links stay plain relative Markdown links.
   No `[[wikilinks]]`, embeds (`![[...]]`), or other Obsidian-only syntax.
2. No Obsidian plugins (such as Dataview or Templater) in the workflow.
   Files must be complete without them.
3. To use Obsidian, open the repo root as a vault and set:
   - Settings → Files & links → Use [[Wikilinks]]: off
   - Settings → Files & links → New link format: Relative path to file
4. `.obsidian/` is ignored by Git, so each person's vault settings stay local.
5. When a spec needs research that isn't a spec or a decision (for example, model comparisons or eval notes for [SPEC-2026-09-26-vendor-neutral-ai-harness](../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md)), add the knowledge layer in this repo's style through that spec or a new decision record: saved sources and LLM-maintained notes under `docs/`, kebab-case names, relative links, with the maintenance rules written into `README.md`.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Plain Markdown links over wikilinks: wikilinks show as literal text on GitHub and in most agents and harnesses.
The cost is slightly more typing when linking by hand in Obsidian; the settings above make Obsidian write relative links for you.

Gitignored `.obsidian/` over a committed vault config: avoids churn from workspace and plugin state.
The risk is someone linking with wikilinks by default; rule 1 and review catch it.

Deferring the knowledge layer: nothing needs it yet.
The risk is research landing in ad hoc places; rule 5 names where it goes when it's needed.

### Dependencies

[Conventions](2026-09-26-conventions.md), [Structure](2026-09-25-structure.md).

### Interfaces

Obsidian (optional), any Markdown viewer, GitHub.

## Key Results and retrospective feedback
