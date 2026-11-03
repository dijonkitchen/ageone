# Decision Record 2026-11-02: place-outcomes Data and Stack

## Status timeline

2026-11-02: Proposed by Claude, at JC's request

2026-11-02: Accepted by JC

2026-11-02: Amended by Claude, while building: the committed test data is a 40-ZIP sample of Zillow's file, credited to Zillow, since the loop's tests need its monthly layout; Zillow's terms allow free public use with attribution. FHFA stays the cross-check.

2026-11-03: Amended by Claude, while building milestone 2: SEDA downloads by script once Mozilla's root store (certifi) is trusted, since its chain ends at an emSign root this environment lacks, but downloading it means accepting its data use agreement, which bars republishing its files, so JC accepts it, tests use made-up scores, and the report stays local. Crosswalks are the Census 2010 ZCTA to tract file (population weights, no token, matching the Atlas's 2010 tracts) and NCES's 2024 district to ZCTA file (land area weights), in place of HUD's token-gated crosswalk. Question 1's baseline is area income and state, because the Atlas outcome already fixes parental income at the 25th percentile. EPA walkability and FEMA risk wait for a later change: their download URLs returned 404 and 403 from this environment.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Settle the four open questions in [the spec](../../specs/SPEC-2026-11-02-place-outcomes.md) with checks on the real files, so code starts from sources that are reachable, licensed for the use, and informative.

#### Non-functional

Every source downloads with a script and no account, or the exception is named.
Committed test data only from sources that allow redistribution.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Requesting raw survey microdata, or scraping pages that block scripts.

#### Non-functional

## Decision

Started from the python project template, with the same tools as [mle-lab](../../../mle-lab/docs/decisions/2026-10-16-mle-lab-stack.md): DuckDB for data and features, MLflow for tracking, the registry, and serving, and scikit-learn for the models.

1. **Home values: Zillow ZHVI by ZIP, monthly.**
   Zillow's metrics page says the data "is free for public use by consumers, media, analysts" and that "proper and clear attribution of all data to Zillow is required" ([Zillow real estate metrics](https://www.zillowgroup.com/developers/api/public-data/real-estate-metrics/)).
   The ZIP file (`files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv`, 124 MB) downloaded by script on 2026-11-02 and holds 1,543 California and 547 New Jersey ZIPs, monthly from January 2000 through September 2026.
   FHFA's annual ZIP5 and tract indexes (`fhfa.gov/hpi/download/annual/hpi_at_zip5.xlsx`, `hpi_at_tract.csv`; [datasets page](https://www.fhfa.gov/data/hpi/datasets)) are public and reachable; they back the committed test data and cross-check Zillow.
2. **Student wellbeing: hand-entered districts, not statewide.**
   The Healthy Kids Survey has no bulk download found; [kidsdata.org](https://www.kidsdata.org) publishes district tables (unweighted, two school years pooled), but its pages block scripted requests from this environment.
   Questions 1 and 2 run statewide without wellbeing; a hand-entered CSV of districts, one source link per row, feeds a separate wellbeing analysis.
3. **Cross-state school measure: SEDA 2025.2.**
   It has school and district CSVs with covariates and a crosswalk ([SEDA downloads](https://edopportunity.org/trends/data/downloads/)), cited as "Stanford Education Data Archive (Version SEDA 2025.2)".
   Its host (`stacks.stanford.edu`) fails TLS verification from this cloud environment, so the files are fetched once on a laptop into the local cache; the fetch step accepts a local path.
4. **Unit: ZIP code**, because home values come by ZIP; tracts join with HUD's ZIP-to-tract residential weights (free token) and districts through SEDA's crosswalk.

### Checks behind the decision

The Opportunity Atlas tract file (`www2.census.gov/ces/opportunity/tract_outcomes_simple.csv`, 34 MB) downloaded by script and has the adult income rank for children of 25th-percentile parents (`kfr_pooled_pooled_p25`) for 7,950 of 8,012 California tracts and 1,992 of 2,002 New Jersey tracts.
The 10th to 90th percentile spread is 0.38 to 0.53 in California and 0.36 to 0.57 in New Jersey, so there is variation to explain.

The forecast gate's two baselines, scored on every ZIP-month with a 12-month label, as mean absolute error of the log change in ZHVI:

| State | Years | No change | Momentum |
|-------|-------|-----------|----------|
| CA | 2001-07 | 14.2% | 9.1% |
| CA | 2008-11 | 9.9% | 11.1% |
| CA | 2012-19 | 9.0% | 6.8% |
| CA | 2020-25 | 7.1% | 7.9% |
| NJ | 2001-07 | 10.3% | 4.9% |
| NJ | 2008-11 | 6.3% | 5.2% |
| NJ | 2012-19 | 4.1% | 3.6% |
| NJ | 2020-25 | 7.9% | 5.0% |

Neither baseline wins every period (momentum fails at turning points), so beating both is a real bar.
ZHVI is smoothed, which flatters momentum; the forecast uses only values published by each as-of month.

### Choices and Tradeoffs/Risks

- Zillow over FHFA for the loop: monthly labels give about 300 forecast months to replay, against about 25 annual ones; FHFA stays as the public cross-check.
- Wellbeing is the factor JC's scorecard weighs as "low pressure", but without a bulk source it can't be statewide; the hand-entered subset keeps it in the analysis without scraping.
- SEDA needs one manual fetch; if that stops working, CAASPP (California) and NJSLA (New Jersey) give within-state school measures, but not on one scale.

## Consequences

The project can be built and tested with no accounts except HUD's free token, and one manual SEDA download.
