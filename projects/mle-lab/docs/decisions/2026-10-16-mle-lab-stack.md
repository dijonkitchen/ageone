# Decision Record 2026-10-16: mle-lab Stack

## Status timeline

2026-10-16: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-10-16-mle-lab.md) that covers every stage of an ML system (data, features, training, tracking, registry, serving, monitoring, and a retraining loop) with tools that are common in industry, so what's learned here carries over.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
Runs on a laptop with no services to stand up.

### Nice to haves

#### Functional

Each tool can later be swapped for its hosted counterpart (a remote MLflow server, a warehouse) without rewriting the stages.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A feature store, orchestrator, or monitoring service before the plain loop is understood.

#### Non-functional

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
Python is the ecosystem for ML, which [Languages for Agentic Work](../../../../docs/decisions/2026-10-08-languages-for-agentic-work.md) keeps.

- **Python 3.12 with uv**, from the template.
- **DuckDB 1.5** for data and features: SQL straight over Parquet, in process, with one file as the warehouse holding features, predictions, and evaluations.
- **MLflow 3.17** for tracking, the model registry, evals history, and serving.
  Its default tracking URI is now `sqlite:///mlflow.db` in the working directory (checked in `mlflow/store/tracking/__init__.py` of the installed version), so the registry works with no server.
  Models move by aliases (`champion`, `challenger`), which replaced stages.
- **scikit-learn 1.9** for models, as pipelines, so preprocessing ships inside the model.
- **pandas 3** between DuckDB and scikit-learn.

### High-level C4(context/container/component/code) diagram

```
raw Parquet --DuckDB SQL--> features --> train --> MLflow run + registered version (challenger)
                                                        |
                                    evals on newest labeled month, gates
                                                        v
                         champion alias --> score / mlflow models serve --> predictions
                                                        |
                         labels land --> monitor (PSI drift, served evals) --alert--> retrain
```

### Choices and Tradeoffs/Risks

- Generated data over a public dataset: a public dataset is fixed, but the loop needs data that changes on cue, with labels that arrive month by month.
- MLflow saves scikit-learn models with skops instead of pickle by default.
  skops refuses types it can't vet, such as the gradient boosted tree's predictor, so training names that one type as trusted; it is safe only because we trained the model ourselves.
- `mlflow models serve` starts `uvicorn` from `PATH`, so `mle serve` puts the project's environment first.
- PSI over deciles of the training data, or value by value for categories and counts with few values: simple and standard, but blind to changes in how features relate to each other; served evals catch those once labels land.
- Ties promote the challenger: on equal evals, the model trained on newer data wins.

### Dependencies

### Interfaces

`mle` CLI, the DuckDB tables `features`, `predictions`, and `evaluations`, and the MLflow registered model `churn`.

## Key Results and retrospective feedback
