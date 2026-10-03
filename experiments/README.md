# Experiments

Each experiment asks one question and compares variants of one choice on the same cases and models ([SPEC-2026-09-27-eval-benchmark-pages](../specs/SPEC-2026-09-27-eval-benchmark-pages.md)).
[`site/build`](../site/build) publishes every experiment here as a page; adding a folder is enough.

## Run

```sh
experiments/run formats --estimate     # calls, tokens, and estimated cost per model; no model calls
experiments/run formats --yes          # run it (OPENROUTER_API_KEY), writing experiments/formats/results/
experiments/run formats --self-check   # reference solutions pass and null baselines fail; recorded for the page
site/build                             # rebuild _site/ from committed files
```

Without `--yes`, a run stops after printing the estimate.
`--model`, `--reps`, and `--variant` override the experiment's defaults; frontier models and extra repetitions are opt-in this way.

## Folder format

`experiments/<id>/`:

- `experiment.json`:
  - `question`: the one question it answers.
  - `answer`: a one-line answer for the index, or `null` until it has run.
  - `decision`: the repo path of the decision record it informs.
  - `models`: roles or `provider/model` IDs to run by default, and `reps`: repetitions per case.
  - `variants`: `id`, `label`, `harness` (`pi`, `claude-code`, or `direct`), and `cases`, a folder of eval cases relative to the experiment, or `evals/...` to reuse the repo's cases.
  - `outside` (optional): results from outside benchmarks, shown apart from ours, each with `source`, `url`, and `rows` of `[label, result]`.
- `README.md`: `# Title`, then `## Question`, `## Setup`, `## Conclusion`, and `## Not measured`, rendered on the page.
- Case folders in the [eval case format](../evals/README.md#cases), with a reference solution each.
- `results/`: NDJSON written by `experiments/run`, one line per case, variant, model, and repetition; commit it.

When a run settles the question, write the conclusion in `README.md`, set `answer`, and amend the decision record (or write a new one).
