# mle-lab

A small, complete ML system on real market data, built to learn ML engineering by iterating on it.
After each close it forecasts the S&P 500's volatility over the next week, learns from the labels that arrive five days later, and retrains behind an eval gate.
See the [spec](specs/SPEC-2026-10-16-mle-lab.md) and the [stack decision](docs/decisions/2026-10-16-mle-lab-stack.md).
It is an exercise, not investment advice.

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run mle fetch        # download the S&P 500 and VIX from FRED (no key) and build features
uv run mle replay       # run the daily loop over every trading day since 2019, then summarize by year
uv run mlflow ui        # browse training runs, coefficients, and model versions at http://127.0.0.1:5000
uv run mle step         # today's forecast, monitoring, and a retrain if one is due
uv run mle serve        # serve the champion over HTTP on port 5001
```

Ask the served model for a forecast (volatilities as fractions, so 0.15 is 15%):

```sh
curl -s localhost:5001/invocations -H 'Content-Type: application/json' \
  -d '{"dataframe_records": [{"rv_1d": 0.12, "rv_5d": 0.14, "rv_21d": 0.13, "vix": 0.17}]}'
```

Query the loop's history, for example every day the champion fell behind the baseline:

```sh
uv run python -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb', read_only=True).sql(
  'SELECT date, model_version, round(model_qlike, 3) AS model, round(baseline_qlike, 3) AS baseline, retrained, promoted FROM monitoring WHERE alert LIKE \'%behind%\' ORDER BY date'))"
```

## The stages

| Stage | Command | Module | What it teaches |
|---|---|---|---|
| Data | `fetch` | `data.py` | Pulling a real source, and keeping data you may not redistribute out of git. |
| Features | `build` | `features.py` | Window functions in DuckDB SQL; a label that arrives late; checks that stop bad data. |
| Model | `bootstrap` | `model.py` | Training only on what was known, tracking in MLflow, registering versions, and a gate against a baseline. |
| Serving | `serve` | `serve.py` | The champion over HTTP with `mlflow models serve`. |
| Loop | `step`, `replay` | `loop.py` | Daily forecasts, monitoring on arriving labels, and retraining when the model falls behind or goes stale. |

## Things to try

Each is a small change whose effect shows in the next `mle replay` and `mle summary`:

- Drop the VIX from `FEATURES` in `config.py` and see how much of the edge it carries.
- Add a model (a gradient boosted tree, say) to `model.py` and let the gate pick between them.
- Change `MONITOR_DAYS`, `RETRAIN_DAYS`, or `COOLDOWN_DAYS` in `loop.py` and watch retrains and quality trade off.
- Retrain every day instead of on alerts, and see whether the extra versions buy anything.
- Set `HORIZON` to 1 or 21 days.
