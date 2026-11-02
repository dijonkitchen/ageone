# place-outcomes

Schools, homes, and outcomes by place, for California and New Jersey ([spec](specs/SPEC-2026-11-02-place-outcomes.md)).

This first milestone is the ML engineering loop: forecast every ZIP code's home value change over the next 12 months, score the forecasts as their labels arrive, and retrain behind an eval gate.
The outcomes and price analyses (questions 1 and 2 of the spec) come next.

Data provided by Zillow: the [Zillow Home Value Index](https://www.zillowgroup.com/developers/api/public-data/real-estate-metrics/) by ZIP, all homes, middle third of values, smoothed and seasonally adjusted, monthly.

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run places fetch            # download Zillow's ZIP file (about 124 MB) and build features
uv run places replay           # bootstrap as of 2012-01, then run the loop every month to the latest
uv run places summary          # error by origin year: model, no change, and momentum
uv run mlflow ui               # runs, registered versions, aliases, and gate tags
```

`places step` runs one month of the loop, and `places bootstrap` trains and promotes a first champion.
Everything is written under `data/`, `mlflow.db`, and `mlruns/`, which git ignores.

## How it works

- **Features** (DuckDB SQL, one row per ZIP and origin month): log changes over 1, 3, 6, 12, 24, and 60 months, 12-month volatility, the ZIP's level against its state's median, state and metro momentum, month of year, and state.
  A row uses only values for months up to its own, and tests check that rebuilding on data cut at a month gives the same features.
- **Label**: the log change in home value over the next 12 months, known only 12 months later.
- **Model**: scikit-learn's histogram gradient boosted regressor, logged and registered in MLflow.
- **Gate**: on the newest 12 labeled origin months, a challenger must beat both baselines, no change and momentum (the next year repeats the last), on mean absolute error, and do at least as well as the champion unless the champion has fallen behind a baseline.
  Training stops 12 months before the eval window, so no training label covers a month after any eval origin.
- **Loop**: each month, forecast every ZIP, score the forecasts whose labels just arrived over the last 6 origin months, and retrain when the champion falls behind a baseline or is 12 months old, at most every 3 months.

## Last full replay

As of 2012-01 through 2026-09 on all 2,090 California and New Jersey ZIPs (run 2026-11-02, about 4 minutes): mean absolute error of the 12-month log change, in percentage points.

| Origin year | Model | No change | Momentum |
|-------------|-------|-----------|----------|
| 2012 | 8.41 | 12.08 | 13.95 |
| 2013 | 4.06 | 11.71 | 6.45 |
| 2014 | 4.22 | 6.99 | 5.93 |
| 2015 | 5.49 | 6.38 | 3.66 |
| 2016 | 7.01 | 6.87 | 4.11 |
| 2017 | 6.76 | 8.38 | 3.84 |
| 2018 | 4.19 | 4.31 | 6.05 |
| 2019 | 4.34 | 5.09 | 3.99 |
| 2020 | 8.87 | 14.40 | 9.81 |
| 2021 | 4.66 | 11.82 | 6.18 |
| 2022 | 8.69 | 4.78 | 12.23 |
| 2023 | 6.30 | 5.61 | 5.80 |
| 2024 | 4.66 | 3.25 | 4.61 |
| 2025 (to Sept) | 5.33 | 2.94 | 3.41 |
| **All** | **5.94** | **7.51** | **6.47** |

The model beats both baselines over the whole replay, and wins at turning points (2012 to 2014, 2020 to 2021), where one baseline or the other fails badly.
It loses in calm trending years to momentum (2015 to 2017), and since 2022 to no change: from 2023 every challenger failed the gate, so the 2022 champion kept serving.
There were 47 retrains and 7 promotions.

Caveats:

- Zillow publishes only its latest vintage, which includes revisions and smoothing, so the replay sees slightly cleaner history than a forecaster did at the time.
- When no challenger passes the gate, the stale champion keeps forecasting even while a baseline beats it; falling back to the better baseline is a possible next step.
