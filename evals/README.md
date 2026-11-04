# Evals

Cases drawn from this repo's own tasks, run through a harness against any model, so switching a model, prompt, or harness rests on measurement ([SPEC-2026-09-26-vendor-neutral-ai-harness](../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md)).

## Run

```sh
evals/run --self-check                         # graders: reference solutions pass, the null baseline fails (no keys)
evals/test/run                                 # the runner against a local mock model (no keys)

export OPENROUTER_API_KEY=...
evals/run --model default --model cheap        # every case through pi, 3 repetitions each
evals/run --harness claude-code --model openrouter/anthropic/claude-sonnet-5 --case write-spec
evals/run --harness direct --model openrouter/deepseek/deepseek-v4.1-flash --case read-csv-total
evals/report                                   # summarize everything in evals/results/
evals/report --failures --split train          # failed train runs by case and harness, with transcript paths
```

`--model` takes a role from [`harness/models.json`](../harness/models.json) or a `provider/model` ID, and repeats.
`--harness` is `pi` (default), `claude-code`, `direct` (one model call, no harness or tools), `reference`, or `null`.
`evals/run --help` lists the rest.

The runner refuses to start unless the provider's key is set (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`), so no run bills credentials it happens to find on the machine.
Harnesses get only those keys, search API keys (such as `EXA_API_KEY`), and proxy settings: no cloud credentials or tokens.

## Cases

One folder per case in `cases/`, named by its kebab-case ID:

- `case.json`: `id`, `title`, `source` (the task or rule it comes from), `prompt`, and optional `split` (`train`, the default, or `test`; see [Tuning](#tuning)), `mode` (`agent`, the default, or `direct`), `needs` (such as `["web"]`), `timeoutSec`, and `maxTurns`.
- `setup.sh` (optional): turns the sandbox into the case's starting state.
- `check.sh`: the grader; exit 0 is a pass.
  It runs in the sandbox and can use the helpers in [`lib/check.sh`](lib/check.sh) with `source "$EVALS_LIB/check.sh"`; `$CASE_DIR` is the case folder and `$REPO_ROOT` the repo.
  Direct cases read the model's answer from `$EVAL_OUTPUT`.
- `reference.sh`: a known-good solution, which `--self-check` runs through the grader alongside a null baseline that does nothing.

Each run gets a fresh sandbox: a copy of the repo's tracked and new files without `evals/cases/` and `evals/results/` (so no model can read the graders or earlier answers), committed to its own Git history so graders can diff against the start.
Direct cases get an empty directory.

Grade deterministically where possible.
Add a case for every task a model fails, and turn completed tasks into regression cases; with `--keep`, each run's sandboxes stay in its temporary directory for that.

## Results

`results/<date>-<harness>-<model>.jsonl` holds one JSON line per case, model, and repetition:
`case` and its `split`, `pass`, `score`, `tokens_in` (cache reads and writes included), `tokens_out`, `cache_read`, `cost_usd`, `turns`, `wall_ms`, the `served_model` reported by the provider, `harness` and `harness_version`, `date`, `commit`, and `dirty`, `transcript`, plus `experiment` and `variant` for [SPEC-2026-09-27-eval-benchmark-pages](../specs/SPEC-2026-09-27-eval-benchmark-pages.md) pages.

Every run also saves its transcript (the pi session JSONL, Claude Code's JSON output, the direct request and response, or the reference script's output) to `results/transcripts/<start time>-<harness>-<model>/<case>-<rep>.<ext>`, which is git-ignored; `transcript` is that path relative to the results folder.

Runs that could not be graded go to the matching `.infra.jsonl` with a `status` of `infra_error`, `timeout`, `truncated`, `refused`, or `model_mismatch` (the served model differs from the requested one), and never count as model failures.
Running out of turns is a model failure.

`evals/report` prints pass rate with its range across repetitions, train and test pass rates apart, cost per completed task (total cost over passes), mean tokens, turns, and time.
A difference smaller than the range is noise.
Commit results so trends stay visible.

## Tuning

To improve a prompt, skill, or harness setting against the evals without overfitting to them ([Eval Hill-Climbing](../docs/decisions/2026-10-05-eval-hillclimbing.md)):

1. Measure the baseline on the `cheap` role: `evals/run --model cheap`, then `evals/report`, and note the **Test** pass rate.
2. Read the failures: `evals/report --failures --split train`, then open the listed transcripts.
   Read only `train` transcripts and graders; never look at why a `test` case failed, or it stops measuring generalization.
3. Change one thing, rerun on `cheap`, and repeat from step 2 while the train score improves.
4. Report the test score before and after, then confirm the winning change once on `default` (frontier models only by opt-in, as in [experiments](../experiments/README.md)).
5. Call a change real only when it clears the noise: the 95% interval half-width is about `1/sqrt(cases × reps)`, about ±16 points for 13 cases at 3 repetitions, so grow the case set before judging small changes.

`test` holds out whole kinds of task, not random cases: today every spec and priority-table editing case (`write-spec`, `claim-next-spec`, `sort-priority-table`).
New cases default to `train`; put a new case in `test` only before anyone has read its transcripts, and never move a case out of `test` once its results have been read.
