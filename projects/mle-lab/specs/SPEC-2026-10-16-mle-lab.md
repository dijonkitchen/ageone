# SPEC-2026-10-16-mle-lab: ML Engineering Lab

A small but complete machine learning system to learn ML engineering on, end to end: data, features, training, tracking, a model registry, serving, monitoring, and a feedback loop that retrains on new labeled data behind evals.
It runs on a laptop with no cloud services, using DuckDB for data and MLflow for tracking, the registry, and serving.

The task is monthly churn prediction for a subscription service, on generated data so every run is reproducible and the data can change on purpose: partway through, a pretend app release shifts the inputs (fewer logins, more support tickets) and what they mean (tickets predict churn more strongly), so monitoring has something real to catch and retraining something real to fix.

## Functional requirements

- **Data**: a seeded generator writes raw customers, events, and monthly churn labels as Parquet, with new signups each month and a release month after which inputs and their relation to churn change.
- **Features**: DuckDB SQL reads the raw Parquet and builds a point-in-time features table: each customer snapshot uses only events before it, so no feature leaks the month it predicts.
  Data quality checks (no rows, duplicates, nulls, negative values, an implausible label rate) stop the pipeline when they fail.
- **Training**: scikit-learn pipelines (preprocessing and model in one object, so serving runs exactly what training did), a logistic regression and a gradient boosted tree.
  Each run trains on earlier months and is measured on a later one, and logs to MLflow its parameters, the months it trained on, its input datasets with digests, metrics, and the model with a signature and input example.
- **Registry**: each trained model is registered as a new version of one MLflow registered model and gets the `challenger` alias.
- **Evals and promotion**: an eval scores a version on one labeled month: ROC AUC, PR AUC, log loss, Brier score, calibration gap (mean prediction against the actual rate), and ROC AUC per plan.
  Gates set the minimums a model must meet.
  The challenger becomes `champion` only if it passes the gates and does at least as well as the champion on the same month, or the champion itself fails the gates.
  Every eval is kept in a DuckDB `evaluations` table and an MLflow experiment, and the decision and its reason are tagged on the model version.
- **Serving**: batch scoring of a month with the champion into a DuckDB `predictions` table, and an HTTP endpoint for the champion through `mlflow models serve`.
- **Monitoring**: once a served month's labels land, compare its features with the serving model's training data (population stability index per feature), evaluate the predictions actually served against the gates, and alert on drift, an ROC AUC drop, or a failed gate.
  Reports are written as JSON and logged to MLflow.
- **Feedback loop**: one turn per month scores it, monitors it once labels land, and on an alert (or when forced) trains challengers on the latest labeled months and evaluates them on the newest one, promoting only through the gates, so the next month is served by whichever model earned it.
- **CLI**: `mle` runs each stage on its own (`generate`, `features`, `train`, `promote`, `score`, `monitor`, `serve`), one loop turn (`turn --month M`), or everything (`all`).

## Non-functional requirements

- Local only: no accounts, keys, or network after install; MLflow uses its default SQLite store in the working directory.
- Reproducible: seeded generation and training, so the same command gives the same numbers.
- Readable: each stage is one short module that says what it does and why, so it can be read as a course.
- Fast: tests run in about a minute, and `mle all` in a few minutes on a laptop.
- Current: MLflow 3 and DuckDB 1.5 APIs (model registry aliases rather than the deprecated stages, models logged by `name`).

## Out of scope

- Hosted infrastructure (a remote tracking server, a feature store, Kubernetes), deep learning, and real customer data.
  A later spec can swap any one in once the local loop is understood.

## Definition of done

1. A stack decision in `projects/mle-lab/docs/decisions/` names the tools and why.
2. `make check` passes in `projects/mle-lab/` and in its CI job.
3. Tests show: features use only events before each snapshot; quality checks catch bad data; training logs its run and registers a challenger; promotion follows the gates; the champion answers over HTTP through MLflow's scoring server; and monitoring raises no alert before the release and catches the drift after it.
4. A test runs the feedback loop over the production months and shows it retrains after the release, promotes a challenger trained on post-release data, and serves later months with it within the gates.
5. The project README explains how to run the system and how to look at runs, versions, and evals in the MLflow UI.
