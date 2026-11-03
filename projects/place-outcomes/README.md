# place-outcomes

Schools, homes, and outcomes by place, for California and New Jersey ([spec](specs/SPEC-2026-11-02-place-outcomes.md)).

It does two things:

- **Outcomes and prices** (questions 1 and 2): join school, neighborhood, and adult outcome data by ZIP, and measure what those factors line up with: how children from lower-income families fared as adults, and what homes cost.
- **Forecast loop** (question 3): forecast every ZIP code's home value change over the next 12 months, score the forecasts as their labels arrive, and retrain behind an eval gate.

Data provided by Zillow: the [Zillow Home Value Index](https://www.zillowgroup.com/developers/api/public-data/real-estate-metrics/) by ZIP, all homes, middle third of values, smoothed and seasonally adjusted, monthly.

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run places fetch --seda     # download every source (see below for SEDA's agreement) and build
uv run places replay           # bootstrap as of 2012-01, then run the loop every month to the latest
uv run places summary          # error by origin year: model, no change, and momentum
uv run mlflow ui               # runs, registered versions, aliases, and gate tags
uv run places outcomes         # question 1: factors against adult outcomes
uv run places price            # question 2: factors against home values, and the school premium
uv run places report           # both, as data/report.html
```

**SEDA's agreement**: the school data comes from the Stanford Education Data Archive, and downloading it means accepting its [data use agreement](https://edopportunity.org/trends/data) (enter your email there), which bars republishing its files in full or in part.
Accept it before running `fetch --seda`; without `--seda`, everything but the school measures still builds.
The report includes ZIP-level values derived from SEDA, so it stays in the git-ignored `data/` folder.
To highlight your own ZIPs in the report, list them in a git-ignored `places.local.toml` as `zips = ["94501"]`.

`places step` runs one month of the loop, and `places bootstrap` trains and promotes a first champion.
Everything is written under `data/`, `mlflow.db`, and `mlruns/`, which git ignores.

## How the outcomes and price analyses work

- **ZIP factors**: Opportunity Atlas tract outcomes and covariates (2010 tracts) are averaged into ZIPs weighted by population, using the Census 2010 ZCTA to tract relationship file.
  SEDA district achievement and learning rates (grades 3 to 8, all students, math and reading averaged) are averaged by each district's land area in the ZIP, using NCES's 2024 district to ZCTA relationship file, over the districts SEDA reports.
- **Factors**: school achievement and learning rate, density, high-paying jobs within 5 miles, commute, college share, poverty, single-parent share, plus area income and state as the baseline. Race and ethnicity composition is left out on purpose.
- **Question 1** predicts the adult income rank of children whose parents were at the 25th percentile; **question 2** predicts log home value (the factors plus that outcome).
  Both compare a linear and a gradient boosted model with the baseline, cross-validated with whole counties held out, and report what each factor adds.
- **School premium**: in each state, the home value difference for one standard deviation better school achievement, with and without controls for area income, density, jobs, commute, college share, and poverty.

## How the forecast loop works

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
