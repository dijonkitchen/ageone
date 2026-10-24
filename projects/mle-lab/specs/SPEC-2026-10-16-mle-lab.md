# SPEC-2026-10-16-mle-lab: ML Engineering Lab

A small, complete machine learning system on real data, for a software engineer to learn data science and ML engineering by starting simple and iterating with fast feedback: data, features, training, tracking, a model registry, serving, monitoring, and a feedback loop that retrains on new labels behind eval gates.
It runs on a laptop with DuckDB for data and MLflow for tracking, the registry, and serving.

The task: each morning, forecast every hour of tomorrow's electricity demand on the Texas grid (ERCOT, the ERCO balancing authority), from the U.S. Energy Information Administration's hourly grid data (EIA-930).
It is the forecast grid operators make every day, so there are two bars to measure against.
The floor is a seasonal naive forecast (the same hour last week), which every model must beat to ship.
The stretch goal is the operator's own published day-ahead forecast, which is in the same data.
Labels arrive the day after each forecasted day, and replaying the loop over past years takes a couple of minutes.

History: the first version forecast churn on generated data, and the second forecast S&P 500 volatility from FRED.
JC chose electricity demand because finance data is hard to get and makes it hard to tell whether a forecast is good; both earlier versions are in this branch's history.

## Functional requirements

- **Data**: download EIA-930's six-month balance CSVs (no API key) for a chosen start year onward, and load the hourly demand and the operator's demand forecast for one balancing authority (ERCOT by default) into DuckDB.
  Demand is EIA's adjusted series, which fills reporting gaps.
- **Features**: DuckDB SQL builds one row per hour of each target day from data known by the forecast's cutoff, the end of the day before the forecast is made (so a forecast for day D uses data through D-2, like an operator forecasting D on the morning of D-1): hour, day of week, day of year, federal holiday, demand at the same hour two days and seven days before, and the mean, minimum, and maximum of demand on D-2.
  Data quality checks (missing hours, implausible demand, too little history) stop the pipeline when they fail.
- **Model**: a scikit-learn gradient boosted regressor trained only on target days whose labels were known at its as-of date, with the newest four weeks held out to judge it.
  Each run logs to MLflow its dates, input datasets with digests, metrics (MAPE and RMSE for the model, the seasonal naive forecast, and the operator), and the model with a signature, and is registered as a new version with the `challenger` alias.
- **Gate**: on the same held-out four weeks, the challenger must beat the seasonal naive forecast's MAPE, and do at least as well as the champion unless the champion no longer beats the naive forecast; only then does it get the `champion` alias.
  The decision and its reason are tagged on the version.
- **Serving**: `mlflow models serve` on the champion, taking a target hour's features and returning forecast megawatts.
- **Feedback loop**: each day, forecast tomorrow's 24 hours with the champion next to both bars, score the last 14 days whose labels have arrived, and retrain through the gate when the champion falls behind the naive forecast or its training is four weeks old, at most once a week.
  Forecasts and monitoring are kept in DuckDB, one row per hour and per day.
- **Replay**: bootstrap a champion on a past date and run the loop for every day since, then summarize MAPE by month for the model, the naive forecast, and the operator.
- **CLI**: `mle fetch`, `build`, `bootstrap`, `step`, `replay`, `summary`, `serve`.

## Non-functional requirements

- Real data: EIA data is public domain, so tests run offline on a committed year of real ERCOT hours.
- Honest: on any replayed day, features, training, evaluation, and monitoring use only data known by that day's cutoff, and tests check it.
- Fast feedback: tests run in under a minute, and a replay from 2024 runs in a couple of minutes.
- Small: a handful of short modules, so a change is easy to try and its effect shows in the next replay.

## Out of scope

- Weather forecasts, other regions, and intraday updates: each is a next iteration once the loop is understood.

## Definition of done

1. A stack decision in `projects/mle-lab/docs/decisions/` names the tools and why.
2. `make check` passes in `projects/mle-lab/` and in its CI job.
3. Tests on real committed data show: features are computed correctly and never use data after the cutoff; quality checks catch bad data; training logs its run and registers a challenger; the gate decides as specified; the champion answers over HTTP through MLflow's scoring server.
4. Tests show a replay forecasts every day, retrains through the gate, never trains on labels from after its as-of date, and beats the naive forecast.
5. A replay from 2024 on downloaded EIA data beats the naive forecast's MAPE, its gap to the operator's forecast is reported, and the README shows how to run it and look at runs and versions in the MLflow UI.
