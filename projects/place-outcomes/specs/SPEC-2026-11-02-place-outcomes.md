# SPEC-2026-11-02-place-outcomes: Schools, Homes, and Outcomes by Place

A data science and ML engineering project on public, area-level data.
It joins the factors people weigh when choosing where to live (housing cost, school achievement and growth, student wellbeing, walkability, and disaster risk) with two kinds of outcome: how children who grew up in each place fared as adults, and what homes there cost.
It covers California and New Jersey, the two states whose school and wellbeing sources were checked when this spec was written.
It runs on a laptop with DuckDB for data and MLflow for tracking, like [mle-lab](../../mle-lab/specs/SPEC-2026-10-16-mle-lab.md).

It answers three questions:

1. **Outcomes**: which of today's place factors line up with better adult outcomes for children from the same parental income level?
   The label is the Opportunity Atlas's adult income rank and incarceration rate by tract, for children born 1978 to 1983.
   This is descriptive: families choose where to live, so a factor that predicts outcomes is not shown to cause them.
2. **Price**: how much of a place's home value do the factors explain, what does one standard deviation of school quality cost, and which places have better schools or outcomes than their price implies?
   This is a hedonic model; its residual is the "value" signal.
3. **Forecast**: how much will each ZIP code's home value change over the next 12 months?
   This is the ML engineering loop: a new month of labels arrives, the model is scored and retrained behind an eval gate, and the loop replays over past years in minutes.

Why this shape: outcome labels lag the factors by decades and refresh rarely (the Atlas had releases in 2018, 2024, and 2025), so question 1 is a one-off analysis.
Home values refresh monthly, so question 3 carries the feedback loop that question 1 can't.
The [comparison with mle-lab](https://claude.ai/artifact/VyZ22vmGqaS5CvhQpCUpdn) has the data checks behind this.

## Data

| Factor or label | Source | Level | Refresh |
|-----------------|--------|-------|---------|
| Adult outcomes by parental income | [Opportunity Atlas](https://www.census.gov/programs-surveys/ces/data/public-use-data/opportunity-atlas-data-tables.html) | Tract, county | Irregular (2018, 2024, 2025) |
| Home value, monthly | [Zillow ZHVI](https://www.zillow.com/research/data/) | ZIP code | Monthly, around the 16th |
| Home value, annual | [FHFA local house price indexes](https://www.fhfa.gov/data/hpi/datasets) (developmental) | ZIP code, tract | Yearly |
| School achievement and learning rates, both states on one scale | [SEDA](https://edopportunity.org/trends/methods) | District, school | Roughly yearly; 2025 covers 2009 to 2025 |
| California test results | [CAASPP research files](https://caaspp-elpac.ets.org/caaspp/ResearchFileListSB) (caret-delimited) | School, district | Yearly |
| Student wellbeing (sadness, connectedness, caring adults) | [California Healthy Kids Survey](https://calschls.org/reports-data) | District | Every two years per district; PDF reports, no bulk download found |
| Walkability | [EPA National Walkability Index](https://epa.gov/smartgrowth/smart-location-mapping) | Block group | 2021 release |
| Disaster risk | [FEMA National Risk Index](https://hazards.fema.gov/nri/data-resources) | Tract, county | Periodic |
| Area covariates (income, tenure, commute, age, composition) | ACS 5-year | Tract | Yearly |
| Mortgage rate | Freddie Mac PMMS via FRED | National | Weekly |
| ZIP to tract weights | [HUD-USPS ZIP crosswalk](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) | ZIP, tract | Quarterly; free token |

The unit of analysis is the ZIP code, because home values come by ZIP.
Tract and block group values are averaged into ZIPs with the crosswalk's residential weights, and district values are joined through the districts that serve each ZIP.

## Functional requirements

- **Fetch**: download each source above into a local cache, recording its URL, vintage, and file digest.
  Sources without a bulk download (Healthy Kids Survey) come from a hand-entered CSV with one source link per row.
- **Crosswalk and features**: DuckDB SQL builds one row per ZIP and year with every factor, the label it is scored against, and a count of how many source areas fed each value.
  Data quality checks (crosswalk weights that don't sum to 1, missing factors over a threshold, suppressed cells, implausible values) stop the pipeline when they fail.
- **Outcomes model** (question 1): a linear model and a gradient boosted model predict the Atlas outcome from the factors, compared with a baseline that uses parental income percentile alone.
  Scores use spatial cross-validation, with whole counties held out, so neighbors can't leak into the test fold.
  The report shows each factor's partial dependence and what it adds over the baseline.
- **Price model** (question 2): the same two model types predict log home value from the factors, scored the same way.
  The report gives the price of one standard deviation of school quality in each state, and the ZIPs furthest above and below their predicted value with the factors behind each.
- **Forecast loop** (question 3): forecast each ZIP's 12-month change in home value as of a month, using only data published by then.
  Each run logs to MLflow its dates, data digests, and metrics, and registers a `challenger`.
  The gate promotes a challenger to `champion` only if, on the newest 12 months of matured labels, it beats both a no-change forecast and a momentum forecast (the trailing 12-month change) on mean absolute error, and does at least as well as the champion.
- **Replay**: bootstrap a champion on a past month and step monthly to now, then summarize error by year for the model and both baselines.
- **Report**: `report` writes a static HTML page with the tables and charts for all three questions and a caveats section, ready for the site.
- **CLI**: `places fetch`, `build`, `outcomes`, `price`, `bootstrap`, `step`, `replay`, `report`.

## Non-functional requirements

- Honest about cause: every outcome and price result is labeled as association, and the report links the Opportunity Atlas's own causal estimates rather than reading cause from feature importance.
- No ranking by demographics: race and ethnicity composition may be a control or a described covariate, but never a score that ranks places, because of fair housing concerns.
- Private: nothing personal is committed (no shortlist, budget, or home search).
  Places to highlight in the report come from an uncommitted local config file.
- Honest in time: forecast features, training, and gating use only data published by each as-of month, and tests check it.
- Licenses respected: each source's terms are followed and cited in the README; committed test data comes only from sources that allow redistribution.
- Fast feedback: tests run offline in under a minute on small committed samples of real data, and a replay runs in a few minutes.

## Out of scope

- Individual-level data (Add Health, NLSY97), which needs registrations or restricted contracts.
- Causal estimates of school or neighborhood effects.
- States other than California and New Jersey, listings, and anything that needs scraping.

## Open questions

Settled with scratch analysis before any project code:

1. **Home value source for the loop.** Zillow ZHVI is monthly, which makes the loop real, but its terms need checking for scripted download and for committing samples. FHFA's ZIP indexes are public but yearly, which leaves one label a year. Recommendation: Zillow if its terms allow, FHFA otherwise, and FHFA for committed test data either way.
2. **Student wellbeing at scale.** The Healthy Kids Survey has no bulk download found so far. Options: hand-enter districts of interest, check [kidsdata.org](https://www.kidsdata.org) for district tables, or request raw data from CalSCHLS. Recommendation: run questions 1 and 2 without it statewide, and add it as a separate analysis on the hand-entered districts. New Jersey has no equivalent survey found yet.
3. **Cross-state school measure.** Recommendation: SEDA, which puts both states on one scale; state tests add detail within a state.
4. **Unit.** ZIP code (recommended, matches home values) or school district (matches schools and wellbeing).

## Definition of done

1. A data and stack decision in `projects/place-outcomes/docs/decisions/` settles the open questions and names the tools.
2. `make check` passes in `projects/place-outcomes/` and in its CI job.
3. Tests on committed real samples show: crosswalk weights sum to 1 and aggregate correctly; features match hand-checked values for a few ZIPs; quality checks catch bad data; spatial folds never split a county; the forecast never uses data published after its as-of month; the gate decides as specified.
4. The outcomes and price reports for both states show spatially cross-validated R² for each model and the baseline, the school-quality price per state, and the caveats section.
5. A replay of the forecast loop beats both the no-change and momentum baselines over the replayed years, and the README shows how to run it and view runs in the MLflow UI.
