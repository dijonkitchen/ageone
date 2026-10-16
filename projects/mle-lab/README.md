# mle-lab

A small but complete machine learning system, built to learn ML engineering end to end on a laptop.
It predicts which subscribers churn next month, on generated data that changes on purpose, so every stage has something real to do.
See the [spec](specs/SPEC-2026-10-16-mle-lab.md) and the [stack decision](docs/decisions/2026-10-16-mle-lab-stack.md).

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run mle all          # generate data, build features, bootstrap a champion, then run the loop month by month
uv run mlflow ui        # browse runs, model versions, and evals at http://127.0.0.1:5000
uv run mle serve        # serve the champion over HTTP on port 5001
```

Ask the served model for churn probabilities:

```sh
curl -s localhost:5001/invocations -H 'Content-Type: application/json' -d '{"dataframe_records": [
  {"plan": "basic", "region": "eu", "tenure_days": 30, "logins_30d": 0, "tickets_30d": 3, "payment_failures_30d": 1, "days_since_login": 40}]}'
```

Query what the system stored with DuckDB, for example how every model did on every month:

```sh
uv run python -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb', read_only=True).sql(
  'SELECT snapshot_date, model_version, role, round(roc_auc, 3) AS auc, round(calibration_gap, 3) AS gap, passed FROM evaluations ORDER BY ALL'))"
```

## The stages

Each stage is one module in `src/mle_lab/` and one `mle` command; run `uv run mle --help` for options.

| Stage | Command | Module | What it teaches |
|---|---|---|---|
| Data | `generate` | `data.py` | Seeded raw Parquet: customers, events, monthly churn labels, and a release in month 9 that shifts behavior. |
| Features | `features` | `features.py` | Point-in-time SQL in DuckDB over Parquet, so no feature leaks the future; data quality checks that stop the pipeline. |
| Training | `train` | `train.py` | scikit-learn pipelines tracked in MLflow: params, input datasets with digests, metrics, and a signed model, registered as `challenger`. |
| Evals | `promote` | `evaluate.py`, `registry.py` | Metrics, per-plan slices, and gates on the newest labeled month; the `champion` alias moves only when a challenger earns it. |
| Serving | `score`, `serve` | `serve.py` | Batch scores into DuckDB, and the champion over HTTP with `mlflow models serve`. |
| Monitoring | `monitor` | `monitor.py` | Drift (PSI) against the champion's training data, and evals of what was actually served once labels land. |
| Feedback loop | `turn --month M` | `loop.py` | Score, learn from new labels, retrain on alert, and promote behind the gates. |

## The feedback loop

Months 1 to 7 train the first models and month 8 judges them.
Months 9 to 14 are production: each runs one turn of the loop.

1. Score month M with the champion, before anyone churns.
2. When M's labels land, monitor M: drift against the champion's training months, and evals of the served predictions.
3. On any alert, train challengers on the four labeled months before M and evaluate them on M.
4. Promote a challenger only if it passes the gates and does at least as well as the champion on M.

A run of `mle all` shows the loop at work: the release in month 9 shifts logins and tickets, which shows in month 10's snapshot as drift and a calibration gate failure.
Challengers trained on pre-release months fail the same gate, so the old champion stays.
In month 11 a challenger trained with post-release data passes and is promoted, and later months are served by it within the gates.

Things to try next: change the gates in `evaluate.py`, the drift in `data.py`, or the window in `loop.py`, and watch how the loop reacts; or point `MLFLOW_TRACKING_URI` at a remote MLflow server.
