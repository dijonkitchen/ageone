# SPEC-2026-10-05-eval-hillclimbing: Eval Hill-Climbing

Gives [`evals/`](../evals/README.md) what a tuning loop needs, per [Eval Hill-Climbing](../docs/decisions/2026-10-05-eval-hillclimbing.md): held-out cases, kept transcripts, and a failures view.

## Functional requirements

- `case.json` takes an optional `split` (`train` or `test`, default `train`); the existing cases get one, holding out whole kinds of task.
- `evals/run` saves every case's transcript (pi session, Claude Code output, or direct answer) to a git-ignored folder, and each results line records its path.
- `evals/report` shows train and test pass rates separately, and `evals/report --failures` lists failures grouped by case and harness with their transcript paths.
- `evals/README.md` documents the loop: tune on the `cheap` role reading only train transcripts, report the test score before and after, confirm once on `default`, and call a change real only when it clears the noise.

## Non-functional requirements

- No new dependencies; works with every harness the runner supports.
- No model can read transcripts or graders: the sandbox still excludes them.

## Definition of done

1. `evals/test/run` covers the split, transcript saving, and the failures view against the mock provider, and passes in CI.
2. Every case in `evals/cases/` has a `split`, with at least one whole kind of task in `test`.
3. `evals/README.md` documents the loop.
