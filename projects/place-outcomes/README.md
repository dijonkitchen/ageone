# place-outcomes

Which place factors line up with better adult outcomes for children, how much of a home's value they explain, and where will home values go next year?
California and New Jersey, by ZIP code, on a laptop with DuckDB and MLflow.
See the [spec](specs/SPEC-2026-11-02-place-outcomes.md) and the [stack and data decision](docs/decisions/2026-11-02-place-outcomes-stack.md).

Everything here is association, not cause: families choose where to live.
For causal estimates read [the Opportunity Atlas paper](https://opportunityinsights.org/paper/the-opportunity-atlas/).
Race and ethnicity never enter a model or a ranking.

## Run it

From this folder, inside the root `make shell` environment:

```sh
uv run places fetch     # download the four sources (about 180 MB) and record URL, date, and SHA-256
uv run places build     # tracts to ZIPs with the crosswalk, then the data quality checks
uv run places outcomes  # question 1: spatially cross-validated R² against a parental income baseline
uv run places price     # question 2: hedonic model, and the price of one SD of school score per state
uv run places replay    # question 3: bootstrap in 2014-01, step monthly to now, error by year
uv run places report    # write data/report.html
uv run mlflow ui --backend-store-uri sqlite:///data/mlflow.db   # browse runs and model versions
```

`places bootstrap 2020-06` trains and gates one challenger as of a month; `places step` does so for the newest month.
To mark ZIPs in the report's tables, list them in an uncommitted `places.local.json`: `{"highlight_zips": ["94118"]}`.

## Data

| Source | Used for |
|---|---|
| [Opportunity Atlas](https://www.census.gov/programs-surveys/ces/data/public-use-data/opportunity-atlas-data-tables.html) (Opportunity Insights and the Census Bureau) | Adult income rank and incarceration rate by tract; tract covariates as factors |
| Census Bureau [ZCTA to tract relationship file](https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html) (2010) | Residential weights from tracts to ZIPs |
| [Zillow Home Value Index](https://www.zillow.com/research/data/) by ZIP | Home values, monthly; used with attribution |

`tests/data/` holds slices of these files (four counties, home values from 2012) so tests run offline.

## Not in this stage

Pending, per the [decision](docs/decisions/2026-11-02-place-outcomes-stack.md): SEDA learning rates, state test results, Healthy Kids Survey wellbeing, EPA walkability, FEMA disaster risk, property tax and insurance, and FHFA indexes.

## Results

On the data fetched 2026-11-02 (2,090 ZIPs with home values, 174 in the committed sample); county-held-out five-fold R²:

| Target | Baseline (1990 tract income) | Linear | Boosted |
|---|---|---|---|
| Adult income rank (children from low-income families) | 0.436 | 0.520 | 0.587 |
| Incarceration rate | 0.032 | 0.078 | -0.009 |
| Log home value (baseline: 2016 income) | 0.416 | 0.610 | 0.718 |

Holding the other factors fixed, one SD higher third grade math score goes with +6.4% home value in California and -2.1% in New Jersey (a linear fit within each state, so read it as association).

`places replay --start 2014-01` (about four minutes) steps 153 months; the first champion shipped in 2015-02, and 50 challengers were promoted.
Mean absolute error of the 12-month change in log home value, by year of forecast:

| Year | Model | Momentum | No change |
|---|---|---|---|
| 2015 | 0.0437 | 0.0359 | 0.0640 |
| 2016 | 0.0458 | 0.0415 | 0.0690 |
| 2017 | 0.0517 | 0.0384 | 0.0831 |
| 2018 | 0.0377 | 0.0599 | 0.0432 |
| 2019 | 0.0417 | 0.0399 | 0.0508 |
| 2020 | 0.1222 | 0.0985 | 0.1440 |
| 2021 | 0.0606 | 0.0622 | 0.1176 |
| 2022 | 0.0750 | 0.1224 | 0.0482 |
| 2023 | 0.0582 | 0.0577 | 0.0559 |
| 2024 | 0.0334 | 0.0460 | 0.0324 |
| 2025 | 0.0295 | 0.0342 | 0.0294 |
| **All** | **0.0553** | 0.0588 | 0.0679 |

The model beats both baselines over the whole replay, and in 2018, 2021, and 2022 (when the market turned), but it loses to momentum in most years of steady growth.
Two caveats: the market weight of 0.5 (see `forecast.py`) was picked from 0, 0.5, and 1 by looking at these same replay errors, so the scores are in-sample for that one choice (weight 1 scores 0.0570, still ahead of both); and the first attempt, which let the model forecast the market's own level, lost to no-change in 2024 and 2025 and to momentum overall.
