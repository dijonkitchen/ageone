# SPEC-2026-10-16-mle-lab: ML Engineering Lab

A small, complete machine learning system on real market data, for learning ML engineering end to end by iterating on it: data, features, training, tracking, a model registry, serving, monitoring, and a feedback loop that retrains on new labels behind eval gates.
It runs on a laptop with DuckDB for data and MLflow for tracking, the registry, and serving.

The task is one number a day: the S&P 500's realized volatility over the next five trading days, forecast after each close from daily S&P 500 and VIX closes on FRED.
Volatility clusters, so it is forecastable, and there is an honest bar to clear: the baseline that next week looks like last week.
Each forecast's label arrives five trading days later, so the loop gets real feedback every day, and replaying history runs years of that loop in about a minute and a half.

The first version used generated churn data; JC chose to replace it with this smaller case on real data, for faster feedback (the churn code is in this branch's history).

## Functional requirements

- **Data**: fetch the full daily history of FRED series `SP500` and `VIXCLS` as CSV, with no API key, and load the days both have into DuckDB.
- **Features**: DuckDB SQL computes annualized realized volatility over 1, 5, and 21 days from daily log returns, and the VIX as a fraction.
  The label is the next five days' realized volatility, and it is empty until those days have happened.
  Data quality checks (too little history, nulls, values out of range, gaps) stop the pipeline when they fail.
- **Model**: HAR, a linear regression of log future volatility on log past volatility and log VIX, as one scikit-learn pipeline.
  Training uses only labels known on its as-of date, holds out the newest quarter of them to judge the model, and logs to MLflow its dates, coefficients, input datasets with digests, metrics, and the model with a signature.
  Each trained model is registered as a new version and gets the `challenger` alias.
- **Gate**: on the same held-out quarter, the challenger must beat the baseline's QLIKE (the standard loss for volatility forecasts), and do at least as well as the champion unless the champion no longer beats the baseline; only then does it get the `champion` alias.
  The decision and its reason are tagged on the version.
- **Serving**: `mlflow models serve` on the champion, taking the four features and returning the forecast.
- **Feedback loop**: each trading day, forecast with the champion next to the baseline, score the last 21 forecasts whose labels have arrived, and retrain through the gate when the champion falls behind the baseline or its training is a quarter old, at most once every 21 days.
  Forecasts and monitoring are kept in DuckDB, one row a day.
- **Replay**: bootstrap a champion on a past date and run the loop on every trading day since, then summarize forecast quality by year, model against baseline.
- **CLI**: `mle fetch`, `build`, `bootstrap`, `step`, `replay`, `summary`, `serve`.

## Non-functional requirements

- Real data, but never committed: FRED's S&P 500 series forbids reproduction, so it is fetched into the git-ignored `data/`, and tests use generated data shaped like FRED's CSVs.
- Honest: on any replayed day, training, evaluation, and monitoring use only labels that had arrived by that day's close, and a test checks it.
- Fast feedback: tests run in under a minute, and a replay from 2019 runs in about a minute and a half.
- Small: a handful of short modules, so a change is easy to try and its effect shows up in the next replay.

## Out of scope

- Trading or investment advice: a volatility forecast is the exercise, not a strategy.
- Intraday data, more assets, and models beyond HAR; each is a next iteration once the loop is understood.

## Definition of done

1. A stack decision in `projects/mle-lab/docs/decisions/` names the tools and why.
2. `make check` passes in `projects/mle-lab/` and in its CI job.
3. Tests show: volatility and labels are computed correctly and features never see the future; quality checks catch bad data; training logs its run and registers a challenger; the gate decides as specified; the champion answers over HTTP through MLflow's scoring server.
4. Tests show a replay forecasts every day, retrains through the gate, never trains on labels from after its as-of date, and beats the baseline.
5. A replay from 2019 on real FRED data beats the baseline's QLIKE in every year, and the README shows how to run it and look at the runs and versions in the MLflow UI.
