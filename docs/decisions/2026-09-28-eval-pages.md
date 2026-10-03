# Decision Record 2026-09-28: Eval Pages

## Status timeline

2026-09-28: Proposed by Claude, while implementing SPEC-2026-09-27-eval-benchmark-pages

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Publish every experiment's question, results, and conclusion as a web page built only from committed files, as [SPEC-2026-09-27-eval-benchmark-pages](../../specs/SPEC-2026-09-27-eval-benchmark-pages.md) requires.

#### Non-functional

No server, database, or framework build; readable on a phone and in dark mode; honest about spread.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A static site generator, a charting library, or a dashboard service before plain HTML falls short.

#### Non-functional

## Decision

- **Experiments are folders** under `experiments/<id>/`: `experiment.json` (question, answer, decision record, models, repetitions, variants, outside results), a `README.md` write-up, case folders in the eval case format, and `results/` in NDJSON.
  Variants run through `evals/run`, so experiments and the harness evals share one runner, one results format, and one grader check.
  The format is documented in [experiments/README.md](../../experiments/README.md).
- **`site/build` is one dependency-free Node script** that writes static HTML and inline SVG charts to `_site/`.
  It embeds the commit it was built from and no build time, so the same commit always builds the same site.
- **GitHub Pages, deployed by GitHub Actions** from `main`; every pull request builds the site so a broken page fails CI.
- **A variant is called better only when its lowest pass rate across repetitions beats every other variant's highest.**
  With fewer than two repetitions the page says no variant can be called better.
- **Grader checks are results too:** `experiments/run <id> --self-check` records the reference and null runs, and each page shows them.
- **Outside results** live in `experiment.json` and render in a separate, labeled section, never in our tables.
- **Runs cost money, so they are explicit:** `experiments/run` prints an estimate from OpenRouter's public prices and runs only with `--yes`.

### High-level C4(context/container/component/code) diagram

```
experiments/<id>/ (cases, experiment.json) ──> experiments/run ──> evals/run ──> experiments/<id>/results/*.jsonl
experiments/*/ + results ──> site/build ──> _site/ ──> GitHub Pages
```

### Choices and Tradeoffs/Risks

- A hand-written Markdown subset and SVG chart over libraries: no dependencies to pin or update, but only headings, paragraphs, lists, code, bold, and links render.
  Mitigation: switch to a library if write-ups need more.
- Pass-rate ranges across repetitions over confidence intervals: simple and visible, but coarse with 3 repetitions.
  Mitigation: add intervals when repetitions grow.

### Dependencies

Node.js from the pinned environment, the eval runner from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md), and GitHub Pages set to deploy from Actions.

### Interfaces

- `experiments/run <id> [--estimate | --yes | --self-check]`
- `site/build [--out <dir>]`

## Key Results and retrospective feedback
