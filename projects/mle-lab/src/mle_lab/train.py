"""Train a churn model on DuckDB features, track the run in MLflow, and register it as the challenger."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import duckdb
import mlflow
import mlflow.sklearn
from mlflow.data.pandas_dataset import from_pandas
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mle_lab import features
from mle_lab.config import CATEGORICAL, CHALLENGER, LABEL, MODEL_NAME, NUMERIC, TRAINING_EXPERIMENT, Paths
from mle_lab.data import month_start
from mle_lab.evaluate import scores

ModelKind = Literal["logreg", "hgb"]
SEED = 7
# MLflow saves scikit-learn models with skops, which refuses types it can't vet. We trained this
# model ourselves, so trust the gradient boosting tree type that skops flags.
TRUSTED_TYPES: dict[ModelKind, list[str]] = {
    "logreg": [],
    "hgb": ["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
}


@dataclass(frozen=True)
class Trained:
    run_id: str
    version: str
    metrics: dict[str, float]


def pipeline(kind: ModelKind) -> Pipeline:
    """Preprocessing and estimator in one object, so serving applies exactly what training did."""
    if kind == "logreg":
        prep = ColumnTransformer(
            [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL), ("num", StandardScaler(), NUMERIC)]
        )
        return Pipeline([("prep", prep), ("model", LogisticRegression(max_iter=1000))])
    prep = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)], remainder="passthrough"
    )
    return Pipeline([("prep", prep), ("model", HistGradientBoostingClassifier(max_iter=200, random_state=SEED))])


def train(paths: Paths, kind: ModelKind, train_months: Sequence[int], eval_month: int) -> Trained:
    """Fit on `train_months` and report on `eval_month`, which must come after them."""
    if not train_months or max(train_months) >= eval_month:
        raise ValueError(f"train months {list(train_months)} must all precede eval month {eval_month}")
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        train_df = features.load(con, [month_start(m).isoformat() for m in train_months])
        eval_df = features.load(con, [month_start(eval_month).isoformat()])
    x_train, y_train = features.model_input(train_df), train_df[LABEL]
    x_eval, y_eval = features.model_input(eval_df), eval_df[LABEL]

    mlflow.set_experiment(TRAINING_EXPERIMENT)
    with mlflow.start_run(run_name=f"{kind}-to-{month_start(eval_month - 1):%Y-%m}") as run:
        mlflow.log_params({"model": kind, "train_months": ",".join(map(str, train_months)), "eval_month": eval_month})
        # Record exactly what the model saw, with a digest, so a run can be traced to its data.
        for name, x, y in (("train", x_train, y_train), ("eval", x_eval, y_eval)):
            dataset = from_pandas(x.assign(**{LABEL: y}), source=str(paths.warehouse), targets=LABEL, name=name)
            mlflow.log_input(dataset, context=name)

        model = pipeline(kind).fit(x_train, y_train)
        p_eval = model.predict_proba(x_eval)[:, 1]
        metrics = {f"eval_{k}": v for k, v in scores(y_eval, p_eval).items()}
        mlflow.log_metrics(metrics)

        info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=infer_signature(x_eval, model.predict_proba(x_eval)),
            input_example=x_eval.head(3),
            # Serve churn probabilities, not hard labels.
            pyfunc_predict_fn="predict_proba",
            skops_trusted_types=TRUSTED_TYPES[kind] or None,
        )
    version = str(info.registered_model_version)
    mlflow.MlflowClient().set_registered_model_alias(MODEL_NAME, CHALLENGER, version)
    return Trained(run.info.run_id, version, metrics)


def trained_months(version: str) -> list[int]:
    """The months a registered version trained on, from its run's params."""
    client = mlflow.MlflowClient()
    run_id = client.get_model_version(MODEL_NAME, version).run_id
    assert run_id is not None, f"version {version} has no run"
    return [int(m) for m in client.get_run(run_id).data.params["train_months"].split(",")]
