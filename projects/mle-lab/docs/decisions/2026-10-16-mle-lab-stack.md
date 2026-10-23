# Decision Record 2026-10-16: mle-lab Stack

## Status timeline

2026-10-16: Proposed by Claude, at JC's request

2026-10-19: Amended by Claude, at JC's request, before acceptance: the lab forecasts S&P 500 volatility from real FRED data instead of churn on generated data, for a simpler case with faster feedback.

2026-10-23: Amended by Claude, at JC's request, before acceptance: the lab forecasts electricity demand from EIA-930 instead, because finance data is hard to get and to judge; the grid operator's own forecast is a professional bar to measure against.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-10-16-mle-lab.md) that covers every stage of an ML system (data, features, training, tracking, registry, serving, monitoring, and a retraining loop) on real data with a clear sense of what good looks like, with tools common in industry, so what's learned here carries over.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
Runs on a laptop with no services to stand up and no API keys.

### Nice to haves

#### Functional

Each tool can later be swapped for its hosted counterpart (a remote MLflow server, a warehouse) without rewriting the stages.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A feature store, orchestrator, or monitoring service before the plain loop is understood.
Chasing the operator's accuracy with weather data before the loop around a simple model works.

#### Non-functional

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
Python is the ecosystem for ML, which [Languages for Agentic Work](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) keeps.

- **Data: EIA-930 six-month balance files** (`eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_<year>_<Jan_Jun|Jul_Dec>.csv`): hourly demand, the operator's day-ahead demand forecast, and generation for every U.S. balancing authority, with the same columns since at least 2019, no key, and updated daily (the file fetched on 2026-10-23 held the day before).
  U.S. government publications are public domain ([EIA reuse terms](https://www.eia.gov/about/copyrights_reuse.php)); cite "Source: U.S. Energy Information Administration".
- **DuckDB 1.5** for data and features: it reads the CSVs directly, and SQL builds the lagged features from data known by each cutoff; one file holds demand, features, forecasts, and monitoring.
- **MLflow 3.17** for tracking, the registry, and serving.
  Its default tracking URI is `sqlite:///mlflow.db` in the working directory (checked in `mlflow/store/tracking/__init__.py` of the installed version), so the registry works with no server.
  Models move by aliases (`champion`, `challenger`), which replaced stages.
- **scikit-learn 1.9** for the model: a histogram gradient boosted regressor, which learns the daily, weekly, and seasonal shape from calendar and lag features without tuning.

### High-level C4(context/container/component/code) diagram

```
EIA-930 CSVs --> DuckDB demand --SQL--> features per target hour (data through D-2)
                                         |
              train on days labeled by as-of --> MLflow run + version (challenger)
                                         |
              gate on newest 4 labeled weeks: beat naive and champion (operator reported)
                                         v
   champion alias --> daily 24-hour forecast (DuckDB) / mlflow models serve
                                         |
   actuals arrive --> 14-day MAPE vs naive --behind or stale--> retrain
```

### Choices and Tradeoffs/Risks

- Electricity demand over finance: demand is driven by visible cycles (hour, weekday, season, holidays, heat), so a simple model clearly beats a naive one, and the operator's forecast shows what a professional achieves; S&P 500 volatility was forecastable but hard to judge, and FRED's S&P 500 series may not be redistributed.
- ERCOT (Texas) as the default region, not California: in EIA-930, CAISO's published forecast has drifted to 7–9% MAPE since 2024, worse than the seasonal naive forecast (about 6% in 2025), so it is no bar to aim for; ERCOT's stays at 2.2–2.8% against naive's 8.7%, as do PJM, MISO, and NYISO's (2.4–3.5%), measured on the downloaded 2022–2026 files on 2026-10-23.
  Any region is one setting away.
- Cutoff at the end of D-2 for a forecast of D: the operator publishes its day-ahead forecast on the morning of D-1, so our features use no newer data than theirs; they also have weather forecasts, which we don't yet, so trailing them is expected at first.
- Seasonal naive as the gate and the operator as the stretch bar: a model must clearly add something to ship, and beating professionals is a goal to work toward, not a release condition.
- MAPE as the headline metric: easy to read as "percent off"; demand never nears zero, so MAPE's weakness there doesn't bite. RMSE in megawatts is logged too.
- MLflow saves scikit-learn models with skops, which refuses types it can't vet; training names the gradient boosted tree's predictor as trusted, which is safe only because we trained it ourselves.
- MLflow infers a model's pip requirements by importing everything in a subprocess, which takes seconds per model; training names them instead, so a replay can retrain dozens of times quickly.
- `mlflow models serve` starts `uvicorn` from `PATH`, so `mle serve` puts the project's environment first.
- Daily forecasts and monitoring go to DuckDB rather than MLflow: hundreds of tiny runs would bury the training runs that matter.

### Dependencies

### Interfaces

`mle` CLI, the DuckDB tables `demand`, `features`, `forecasts`, and `monitoring`, and the MLflow registered model `grid-demand`.

## Key Results and retrospective feedback
