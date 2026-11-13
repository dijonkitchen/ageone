# Evals

Cases drawn from this repo's own tasks, run through a harness against any model, so switching a model, prompt, or harness rests on measurement ([SPEC-2026-09-26-vendor-neutral-ai-harness](../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md)).

## Run

```sh
evals/run --self-check                         # graders: reference solutions pass, the null baseline fails (no keys)
evals/test/run                                 # both gateways' settings, and the runner against a mock model (no keys)

export AI_GATEWAY_API_KEY=...
evals/run --model default --model cheap        # every case through pi on the active gateway, 3 repetitions each
evals/run --harness claude-code --model anthropic/claude-sonnet-5 --case write-spec
evals/run --harness direct --model deepseek/deepseek-v4.1-flash --case read-csv-total
evals/run --model default --gateway openrouter # the same role through OpenRouter (OPENROUTER_API_KEY)
evals/report                                   # summarize everything in evals/results/
```

`--model` takes a role from [`harness/models.json`](../harness/models.json), a `creator/model` ID on the active gateway, or a `<route>:<model>` ID such as `openrouter:deepseek/deepseek-v4.1-flash` or `anthropic:claude-sonnet-5` (a vendor's own API), and repeats.
`--gateway` routes roles and plain IDs through another gateway for one run.
`--harness` is `pi` (default), `claude-code`, `direct` (one model call, no harness or tools), `reference`, or `null`.
`evals/run --help` lists the rest.

The runner refuses to start unless the route's key is set (`AI_GATEWAY_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`), so no run bills credentials it happens to find on the machine.
Harnesses get only those keys, search API keys (such as `EXA_API_KEY`), and proxy settings: no cloud credentials or tokens.
Every request carries the gateway's privacy settings and, for open-weight models, the host allowlist ([harness](../harness/README.md)).

## Cases

One folder per case in `cases/`, named by its kebab-case ID:

- `case.json`: `id`, `title`, `source` (the task or rule it comes from), `prompt`, and optional `mode` (`agent`, the default, or `direct`), `needs` (such as `["web"]`), `timeoutSec`, and `maxTurns`.
- `setup.sh` (optional): turns the sandbox into the case's starting state.
- `check.sh`: the grader; exit 0 is a pass.
  It runs in the sandbox and can use the helpers in [`lib/check.sh`](lib/check.sh) with `source "$EVALS_LIB/check.sh"`; `$CASE_DIR` is the case folder and `$REPO_ROOT` the repo.
  Direct cases read the model's answer from `$EVAL_OUTPUT`.
- `reference.sh`: a known-good solution, which `--self-check` runs through the grader alongside a null baseline that does nothing.

Each run gets a fresh sandbox: a copy of the repo's tracked and new files without `evals/cases/` and `evals/results/` (so no model can read the graders or earlier answers), committed to its own Git history so graders can diff against the start.
Direct cases get an empty directory.

Grade deterministically where possible.
Add a case for every task a model fails, and turn completed tasks into regression cases; with `--keep`, each run's sandboxes and pi session JSONL files stay in its temporary directory for that.

## Results

`results/<date>-<harness>-<model>.jsonl` holds one JSON line per case, model, and repetition:
`pass`, `score`, `tokens_in` (cache reads and writes included), `tokens_out`, `cache_read`, `cost_usd`, `turns`, `wall_ms`, the `served_model` reported by the provider, `harness` and `harness_version`, `date`, `commit`, and `dirty`, plus `experiment` and `variant` for [SPEC-2026-09-27-eval-benchmark-pages](../specs/SPEC-2026-09-27-eval-benchmark-pages.md) pages.
`model` includes its route (`vercel:anthropic/claude-sonnet-5`), and `route`, `role`, and `effort` are recorded too.

`cost_source` says where `cost_usd` came from.
`gateway` is what the gateway billed, looked up by each response's generation ID, including surcharges such as Vercel's team-wide zero data retention; `served_hosts` then lists the hosts that served the run.
Otherwise it's the harness's own estimate from list prices (`pi` or `claude-code`), or the API's own figure (`provider`).
OpenRouter's billed cost doesn't include its 5.5% fee on buying credits.

Runs that could not be graded go to the matching `.infra.jsonl` with a `status` of `infra_error`, `timeout`, `truncated`, `refused`, or `model_mismatch` (the served model differs from the requested one), and never count as model failures.
Running out of turns is a model failure.
A turn that ends in an API error doesn't count toward the limit, so pi can retry it; a run whose last call failed is an `infra_error`.

`evals/report` prints pass rate with its range across repetitions, cost per completed task (total cost over passes), mean tokens, turns, and time.
Each route gets its own rows, and a cost marked `*` includes a harness's estimate; `evals/report --pool-routes` combines one model's runs across gateways.
A difference smaller than the range is noise.
Commit results so trends stay visible.
