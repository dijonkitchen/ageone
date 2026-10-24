# Decision Record 2026-10-05: Eval Hill-Climbing

## Status timeline

2026-10-05: Proposed by Claude, at JC's request, after comparing the `/claude-api hillclimb` skill and fastai's practices with [`evals/`](../../evals/README.md)

2026-10-23: Amended by Claude, implementing [SPEC-2026-10-05-eval-hillclimbing](../../specs/SPEC-2026-10-05-eval-hillclimbing.md): the held-out kind is spec and priority-table editing; transcripts go to `results/transcripts/<start time>-<harness>-<model>/`, with paths relative to the results folder; `evals/report --split` filters either view.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Tune a prompt, skill, or harness setting against the evals in rounds (run, read failures, change one thing, rerun) without overfitting to the cases being read.

#### Non-functional

Works with any model or harness the runner supports; stays cheap enough to run often.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

An automated optimizer loop or LLM-judged grading before the case set and live runs exist.

#### Non-functional

## Decision

`evals/` already covers the measuring side: deterministic graders with reference and null baselines, sandboxes that hide graders, repetitions with ranges, served-model checks, infra failures kept apart, and cost per completed task.
What it lacks is what a tuning loop needs, taken from the `/claude-api hillclimb` guide and fastai:

- **Held-out cases.** Each case has a `split` of `train` (the default) or `test`.
  Whoever proposes a change reads only `train` transcripts; the reported result is the `test` score, before and after.
  Hold out whole kinds of task (for example every spec-editing case), not random cases, so a passing test score means the change generalizes, following fastai's [validation set](https://www.fast.ai/posts/2017-11-13-validation-sets.html) advice.
- **Transcripts are kept.** Every run saves each case's transcript next to its results line, so failures can be read after the run without `--keep`.
- **Failures are read worst first.** `evals/report` can list failures grouped by case and harness, each linked to its transcript, like fastai's [`plot_top_losses` and `most_confused`](https://docs.fast.ai/interpret.html).
- **Iterate cheap, confirm once.** Rounds run on the `cheap` role; the winning change is confirmed once on `default`, and on frontier models only by opt-in, as `experiments/` already does.
- **A change counts only above the noise.** With binary pass rates the 95% interval half-width is about `1/sqrt(cases × reps)`, about ±16 points for 13 cases at 3 repetitions, so the case set grows before small changes are judged.

### High-level C4(context/container/component/code) diagram

```
cases (split: train | test) ──> evals/run ──> results/*.jsonl + transcripts
train transcripts ──> proposed change ──> evals/run ──> test score before vs after
```

### Choices and Tradeoffs/Risks

- A `split` field in `case.json` over a separate list: the split travels with the case, but moving a case between splits changes history; never move a case out of `test` after reading it.
- Saving transcripts by default costs disk in `evals/results/`; transcripts go in a git-ignored folder and only results lines are committed.
- Holding out task kinds leaves fewer cases to tune on; acceptable while the goal is generalization, revisit if `train` gets too small to show failures.

### Dependencies

The runner and cases from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md); live rounds need an `OPENROUTER_API_KEY`.

### Interfaces

- `case.json`: optional `split` (`train` or `test`).
- `evals/run`: writes transcripts for every run.
- `evals/report --failures`: failures grouped by case and harness, with transcript paths, and train and test pass rates shown apart.
- `evals/report --split train|test`: limits the summary or the failures to one split.

## Key Results and retrospective feedback
