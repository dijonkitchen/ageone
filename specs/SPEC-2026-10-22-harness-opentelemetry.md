# SPEC-2026-10-22-harness-opentelemetry: Opt-In OpenTelemetry for the Harness and Evals

Lets [`evals/run`](../evals/README.md) and [`harness/pi`](../harness/README.md) send OpenTelemetry traces and metrics over OTLP when asked, so a run's time, tokens, and cost can be seen per case, turn, model call, and tool call in any OTLP backend.
It adds to the JSONL transcripts from [SPEC-2026-10-05-eval-hillclimbing](SPEC-2026-10-05-eval-hillclimbing.md) and does not replace them: transcripts stay the record for grading and tuning, and traces are for finding where time and money go.

It is off by default and repo-wide only for the harness and evals.
Projects add their own telemetry in their own specs if they grow a long-running service; the volatility project needs none, since MLflow tracing already exports OTLP ([MLflow docs](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/export/)).

## Functional requirements

- Opt in with the standard OpenTelemetry variables: telemetry is on only when `OTEL_EXPORTER_OTLP_ENDPOINT` (or a per-signal `OTEL_EXPORTER_OTLP_*_ENDPOINT`) is set, and `OTEL_SDK_DISABLED=true` turns it off.
  With neither set, nothing is loaded and nothing leaves the machine.
- One trace per `evals/run` invocation, with a span per case and repetition, holding the harness's own spans as children: session, turn, model call, and tool call.
  The runner passes its span context to each harness with the W3C `TRACEPARENT` variable, so a harness that honours it nests under the case.
- Spans and attributes follow the OpenTelemetry GenAI semantic conventions (`gen_ai.*`), pinned to one named version in the code, because those conventions are still at Development stability and expect renames ([Dash0](https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained), [Greptime](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)).
- Each case span carries the case ID, split, harness and version, requested and served model, pass, score, tokens, cost, and turns, matching the fields of its results line.
- Each results line gains an optional `trace_id`, so a failure in `evals/report --failures` links to its trace.
- Harnesses:
  - `pi`: one pi package that emits the spans above, pinned in `.pi/settings.json`.
    Either a reviewed, pinned third-party package (candidates: [pi-otel-telemetry](https://cdn.jsdelivr.net/npm/pi-otel-telemetry@1.0.0/README.md), [pi-opentelemetry](https://cdn.jsdelivr.net/gh/devkade/pi-opentelemetry@main/README.md), pi-otel) or a small one of our own; a decision record says which and why.
  - `claude-code`: its built-in telemetry, turned on through its documented variables (`CLAUDE_CODE_ENABLE_TELEMETRY` and the `OTEL_*` exporters; traces are in beta) ([Claude Code monitoring](https://code.claude.com/docs/es/monitoring-usage)).
  - `direct`: the runner emits one model-call span itself.
- Metrics per run: token and cost counters and a case duration histogram, labelled by harness, model, and case.
- A `make` target (or documented command) starts a local OTLP backend from devenv, so traces can be viewed without an account anywhere.

## Non-functional requirements

- Private by default: prompt, completion, and tool argument content are not recorded unless `EVALS_OTEL_CAPTURE_CONTENT=1` is set.
  The defaults send only names, IDs, counts, durations, and outcomes.
- No secrets in telemetry: API keys, `Authorization` headers, and environment values are never attributes; a test checks this against the mock provider.
- The sandbox rules hold: harnesses get only the OTLP and `TRACEPARENT` variables added to their allowlist, never collector credentials beyond an `OTEL_EXPORTER_OTLP_HEADERS` the user sets.
- Off costs nothing: with telemetry off, `evals/run` loads no OpenTelemetry code and its run time and results are unchanged.
- OpenTelemetry packages are pinned devDependencies of the runner, loaded only when telemetry is on, since only one OpenTelemetry SDK can own a process.
- Telemetry failures never fail a run: an unreachable collector logs one warning and the run goes on.

## Definition of done

1. `evals/test/run` covers, against the mock provider and an in-process OTLP receiver: no export when off, the span tree and attributes when on, `trace_id` in results lines, no content by default, and no secrets; it passes in CI.
2. A decision record in `docs/decisions/` picks the pi package and the pinned GenAI conventions version.
3. `evals/README.md` and `harness/README.md` document turning telemetry on, the local backend, and the content flag.
4. One live `evals/run --model cheap` with telemetry on shows a full trace (run, case, turn, model call, tool call) in the local backend for both `pi` and `claude-code`, recorded in the pull request.
