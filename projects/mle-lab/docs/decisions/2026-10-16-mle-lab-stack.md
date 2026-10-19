# Decision Record 2026-10-16: mle-lab Stack

## Status timeline

2026-10-16: Proposed by Claude, at JC's request

2026-10-19: Amended by Claude, at JC's request, before acceptance: the lab forecasts S&P 500 volatility from real FRED data instead of churn on generated data, for a simpler case with faster feedback.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-10-16-mle-lab.md) that covers every stage of an ML system (data, features, training, tracking, registry, serving, monitoring, and a retraining loop) on real data, with tools common in industry, so what's learned here carries over.

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
Chasing forecast accuracy with bigger models before the loop around a simple one works.

#### Non-functional

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
Python is the ecosystem for ML, which [Languages for Agentic Work](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) keeps.

- **Data: FRED CSV downloads** (`fred.stlouisfed.org/graph/fredgraph.csv?id=...`) for `SP500` (the last ten years, daily) and `VIXCLS` (since 1990): free, no key, and reachable from the cloud environment, unlike Stooq, which reset the connection.
- **DuckDB 1.5** for data and features: SQL window functions compute realized volatility and the delayed label, and one file holds prices, features, forecasts, and monitoring.
- **MLflow 3.17** for tracking, the registry, and serving.
  Its default tracking URI is `sqlite:///mlflow.db` in the working directory (checked in `mlflow/store/tracking/__init__.py` of the installed version), so the registry works with no server.
  Models move by aliases (`champion`, `challenger`), which replaced stages.
- **scikit-learn 1.9** for the HAR model, as one pipeline (log transform, linear regression, exp back), so serving runs exactly what training did.

### High-level C4(context/container/component/code) diagram

```
FRED CSV --> DuckDB prices --SQL--> features (rv_1d, rv_5d, rv_21d, vix; label 5 days later)
                                         |
                    train on labels known by as-of --> MLflow run + version (challenger)
                                         |
                    gate on newest labeled quarter: beat baseline and champion
                                         v
     champion alias --> daily forecast (DuckDB) / mlflow models serve
                                         |
     labels arrive --> 21-day QLIKE vs baseline --behind or stale--> retrain
```

### Choices and Tradeoffs/Risks

- Volatility instead of returns: next-day returns are close to unpredictable, so a model's feedback would be noise; volatility clusters, so a simple model clearly beats a naive one and changes show up in the numbers.
- HAR over a tree or neural model: the textbook volatility model, a few coefficients you can read in MLflow, and it trains in milliseconds, so the replay can retrain dozens of times.
- QLIKE as the gate's loss: it is robust to noise in realized volatility as a proxy (Patton 2011), and it punishes forecasting calm before a storm more than the reverse.
  RMSE is logged too; in 2020's crash the model's RMSE was worse than the baseline's while its QLIKE was better.
- FRED's S&P 500 series is copyrighted by S&P Dow Jones Indices, and its notes forbid reproduction without permission, so data is fetched at run time and never committed; tests use generated GARCH data in FRED's format.
  The VIX series is CBOE's and needs citation.
- MLflow saves scikit-learn models with skops, which refuses types it can't vet; training names `numpy.log` and `numpy.exp` as trusted, which is safe only because we built the pipeline ourselves.
- MLflow infers a model's pip requirements by importing everything in a subprocess, which took seconds per model; training names them instead, which cut a replay from 7 minutes to under 2.
- `mlflow models serve` starts `uvicorn` from `PATH`, so `mle serve` puts the project's environment first.
- Daily forecasts and monitoring go to DuckDB rather than MLflow: thousands of one-row runs would bury the training runs that matter.

### Dependencies

### Interfaces

`mle` CLI, the DuckDB tables `prices`, `features`, `forecasts`, and `monitoring`, and the MLflow registered model `sp500-vol`.

## Key Results and retrospective feedback

First replay, 2019-01-02 to 2026-10-15 on FRED data fetched 2026-10-19: QLIKE beat the baseline's in every year (for example 0.734 against 1.385 in 2020 and 0.256 against 0.767 in 2026), with 54 retrains and 29 promotions.
The champion's coefficients put most weight on the VIX.
