# Decision Record 2026-11-02: place-outcomes Stack and Data

## Status timeline

2026-11-02: Proposed by Claude, to settle the open questions of [the spec](../../specs/SPEC-2026-11-02-place-outcomes.md) and name the tools.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

- Join area-level factors to adult outcomes and home values by ZIP code, answer the outcomes, price, and forecast questions, and run the forecast loop behind an eval gate.

#### Non-functional

- Runs on a laptop; tests run offline on committed samples; nothing personal is committed.

### Nice to haves

#### Functional

- Every source in the spec (SEDA, state tests, Healthy Kids Survey, walkability, FEMA risk, tax and insurance).

### Avoid out of scope runaway rabbit hole risks

#### Functional

- Scraping, individual-level data, and causal claims.

## Decision

Python with uv, DuckDB for features, scikit-learn for models, and MLflow for tracking and the registry, the same stack as [mle-lab](../../../mle-lab/docs/decisions/2026-10-16-mle-lab-stack.md).

### Answers to the open questions

1. **Home value source for the loop: Zillow ZHVI** (ZIP code, smoothed and seasonally adjusted, single-family and condo, middle tier), downloaded from Zillow's public research CSV with a recorded digest. Zillow publishes it for free use with attribution; the report cites it. A small slice (174 ZIPs, 2012 onward) is committed as test data, with attribution in the README. If Zillow's terms change, FHFA's yearly ZIP index is the fallback, and the slice would be replaced.
2. **Student wellbeing: left out of this stage.** The Healthy Kids Survey has no bulk download, and New Jersey has no equivalent. It stays a separate analysis on hand-entered districts.
3. **Cross-state school measure: the Atlas covariate for 2013 third grade math scores** (`gsmn_math_g3_2013`), which covers both states on one scale and comes in the same file as the other tract factors. SEDA's download page was not reachable at a stable URL from the build environment, so SEDA growth rates are pending.
4. **Unit: ZIP code.** Tract values are averaged into ZIPs with weights.

### Choices and tradeoffs

- **Crosswalk:** the Census Bureau's 2010 ZCTA to tract relationship file, weighted by the population in the overlap, instead of the HUD-USPS crosswalk, which needs a token. 2010 geography matches the Atlas's 2010 tracts. ZIP Code Tabulation Areas approximate ZIP codes; ZIPs that are only PO boxes have no tract population and drop out.
- **Factors:** the Atlas tract covariates (third grade math score, 2016 median household income, poverty, college, single-parent share, foreign-born share, share with a 15 minute commute, population and job density, jobs within five miles, job growth, two-bedroom rent). Race and ethnicity shares are never features. Walkability (EPA), disaster risk (FEMA NRI), tax, insurance, and state test data are pending: the EPA file is reachable, the NRI download returned 403, and the rest need hand-entry or more work.
- **Baseline for the outcomes models:** the tract's 1990 median household income, a stand-in for parental income, since the Atlas outcomes are for children at the 25th parental income percentile.
- **Spatial cross-validation:** scikit-learn `GroupKFold` on the county of the ZIP's largest tract share, five folds, so a county is never split.
- **Forecast:** a gradient boosted model of the 12-month change in log home value from trailing 3, 6, and 12 month changes, momentum acceleration, the level, and the factors. The challenger trains on months whose labels matured before the gate window, so it never sees the labels it is judged on; the gate scores it on the newest 12 months of matured labels against no-change, momentum, and the champion.
- **As-of rule:** month A is the latest published month. Features at t read months up to t; a label for t exists only when t + 12 <= A. Tests alter every later month and check nothing changes.
- **MLflow:** SQLite store under `data/`, aliases `challenger` and `champion` on one registered model.

### Dependencies

duckdb, pandas, scikit-learn, mlflow; dev: pytest, ruff, mypy, pandas-stubs.

### Interfaces

`places fetch | build | outcomes | price | bootstrap MONTH | step | replay | report`.

## Key Results and retrospective feedback

See the README for the first results.
