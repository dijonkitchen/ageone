# mle-lab

A small, complete ML system on real grid data, built to learn ML engineering by iterating on it.
Each morning it forecasts every hour of tomorrow's electricity demand on the Texas grid (ERCOT), learns from the actuals that arrive the next day, and retrains behind an eval gate.
Two bars show how good a forecast is: the seasonal naive forecast (same hour last week), which a model must beat to ship, and ERCOT's own published forecast, which is the professional bar.
See the [spec](specs/SPEC-2026-10-16-mle-lab.md) and the [stack decision](docs/decisions/2026-10-16-mle-lab-stack.md).
Data: U.S. Energy Information Administration, Hourly Electric Grid Monitor (EIA-930).

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run mle fetch        # download EIA-930 balance files since 2022 (no key, about 45 MB each) and build features
uv run mle replay       # run the daily loop every morning since 2024, then summarize error by month
uv run mlflow ui        # browse training runs, metrics, and model versions at http://127.0.0.1:5000
uv run mle step         # tomorrow's forecast, monitoring, and a retrain if one is due
uv run mle serve        # serve the champion over HTTP on port 5001
```

Ask the served model for one hour's forecast in megawatts (a weekday, 5 p.m., mid-July):

```sh
curl -s localhost:5001/invocations -H 'Content-Type: application/json' -d '{"dataframe_records": [{"hour": 17,
  "dow": 3, "doy": 197, "holiday": 0, "lag_2d": 78000, "lag_7d": 76000, "prev_mean": 65000, "prev_min": 50000, "prev_max": 79000}]}'
```

Query the loop's history, for example every morning the champion fell behind naive:

```sh
uv run python -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb', read_only=True).sql(
  'SELECT as_of, model_version, round(100 * model_mape, 2) AS model, round(100 * naive_mape, 2) AS naive, retrained, promoted FROM monitoring WHERE alert LIKE \'%behind%\' ORDER BY as_of'))"
```

## The stages

| Stage | Command | Module | What it teaches |
|---|---|---|---|
| Data | `fetch` | `data.py` | Pulling a real public source, incrementally and atomically. |
| Features | `build` | `features.py` | Time zones, daylight saving, and lags in DuckDB SQL; a cutoff that keeps the future out; checks that stop bad data. |
| Model | `bootstrap` | `model.py` | Training only on what was known, tracking in MLflow, registering versions, and a gate against a baseline. |
| Serving | `serve` | `serve.py` | The champion over HTTP with `mlflow models serve`. |
| Loop | `step`, `replay` | `loop.py` | Daily forecasts, monitoring as actuals arrive, and retraining when the model falls behind or goes stale. |

## Results

A replay from 2024-01-01 to 2026-10-22 on the files fetched on 2026-10-23 (`mle replay`, about two minutes):

| Forecast | MAPE |
|---|---|
| Model | 5.90% |
| Seasonal naive (same hour last week) | 8.12% |
| ERCOT's published forecast | 2.11% |

The first four bootstraps in January 2024 were rejected because naive beat them over December's holidays and January's cold snap, so the first champion shipped on 2024-01-29; after that the loop retrained 80 times and promoted 29.
The model beats naive in most months, but naive wins in calm stretches such as August 2026, and ERCOT stays far ahead because it forecasts the weather.

## Things to try

Each is a small change whose effect shows in the next `mle replay`:

- Add a temperature forecast for Dallas and Houston (Open-Meteo's historical forecast API needs no key) and see how much of the gap to ERCOT closes.
- Predict demand relative to `prev_mean` instead of in megawatts, so trees can follow load growth past anything in training (a quick test gave 5.98% against 6.21%).
- Change `REGION` and `TIMEZONE` in `config.py` to PJM, MISO, or NYISO, whose forecasts are also strong, or to CISO to see a published forecast worse than naive.
- Change `MONITOR_DAYS`, `RETRAIN_DAYS`, or `COOLDOWN_DAYS` in `loop.py` and watch retrains and quality trade off.
- Retrain every day instead of on alerts, and see whether the extra versions buy anything.
