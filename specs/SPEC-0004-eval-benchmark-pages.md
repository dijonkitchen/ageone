# SPEC-0004: Eval and Benchmark Pages

## Functional requirements

Webpages that publish our evals and benchmarks comparing different ways of doing the same work, across different models, so decisions in this repo rest on our own measurements and anyone can read them.

- An **experiment** asks one question and compares **variants** of one choice, holding everything else fixed.
  Each variant runs on the same cases against more than one model.
  Planned experiments, starting with the choices already open in decision records:
  - Output formats a model reads and writes: CSV, TOON, NDJSON, minified and pretty JSON, `key: value` ([Agent Tool Interfaces](../docs/decisions/2026-09-27-agent-tool-interfaces.md)).
  - Tool interfaces for the same task: an existing CLI (such as `gh`), an MCP server, and an AXI-style wrapper.
  - Harnesses running the same tasks: pi, Claude Code, and OpenCode ([Vendor-Neutral AI Harness](../docs/decisions/2026-09-26-vendor-neutral-ai-harness.md)).
  - Later: prompt and instruction styles, effort or thinking levels, and providers serving the same open-weight model.
- An experiment is a folder of plain files in the repo: the question, the variants, the cases, the models, and the grader.
  Adding one needs no code change to the site.
- Experiments run through the eval runner from [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md), with models chosen by `provider/model` ID and the harness chosen per variant: an agent harness (pi, Claude Code, OpenCode) for task experiments, or `direct` for single model calls such as the format experiment.
  They write their results as committed NDJSON, one line per case, variant, model, and repetition.
- Each run records: pass or fail and score, tokens in and out, cost, turns, wall-clock time, the served model ID, harness and version, date, and the commit it ran on.
  Infra failures, truncation, and refusals are recorded apart from model failures.
- The site has:
  - an index listing every experiment with its question, a one-line answer, the date of its latest run, and the models covered;
  - one page per experiment with the question, the variants, a results table per model (pass rate, tokens, cost per completed task, turns, time), a chart comparing variants, the conclusion, and a link to the decision record it informs;
  - the exact command to rerun it, and links to the raw results and cases.
- Results from outside benchmarks (such as a format's authors' own numbers) may be shown for context, but are labeled as outside and kept apart from ours.
- One command builds the site from the committed results; another runs an experiment.
  Both are AXI-style CLIs ([Agent Tool Interfaces](../docs/decisions/2026-09-27-agent-tool-interfaces.md)).

## Non-functional requirements

- Simple: static HTML generated from the results files, with no server, database, or framework build.
  Hostable on GitHub Pages or opened from disk.
- Honest: every number shows its repetition count and spread; a variant is called better only when the difference exceeds that spread.
  Each page states what was not measured.
  The reference solution and null baseline from SPEC-0002 run through each grader before its numbers are published.
- Reproducible: the pages are generated only from committed files, so rebuilding from any commit gives the same site; rerunning an experiment needs only the command shown and API keys.
- Cheap: experiments default to the `cheap` role and few repetitions; frontier models and extra repetitions are opt-in per run, and the estimated cost is shown before a run starts.
- Readable: works at phone width, in light and dark themes, and with tables that stay readable without the charts.
- Private: cases and results contain no secrets or private data, since the pages are public.

## Definition of done

1. The experiment folder format is documented, and a new experiment appears on the site with no change to the site's code.
2. The output-format experiment (CSV, TOON, NDJSON, JSON) has run on at least three models from at least two vendors, covering both a model reading data and a model writing it, with at least three repetitions per case.
3. The tool-interface or harness experiment has run on at least two models.
4. One command builds the site from committed results, and a CI job builds it on every pull request and publishes it from `main`.
5. The index and each experiment page show the metrics, repetition counts, rerun command, and links above, and each conclusion is recorded as an amendment to, or a new, decision record.
