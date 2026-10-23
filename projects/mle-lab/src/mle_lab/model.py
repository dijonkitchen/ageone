"""Train a demand model, track it in MLflow, and promote it only when it earns it.

The model is a histogram gradient boosted regressor on calendar and lagged-demand features. The bar
it must clear to ship is the seasonal naive forecast (the same hour last week); the grid operator's
own forecast is reported next to it as the professional bar to work toward.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

import duckdb
import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.data.pandas_dataset import from_pandas
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from mlflow.pyfunc import PyFuncModel
from sklearn.ensemble import HistGradientBoostingRegressor

from mle_lab import features
from mle_lab.config import CHALLENGER, CHAMPION, EXPERIMENT, MODEL_NAME, TARGET, Paths

EVAL_DAYS = 28  # The newest four weeks of labeled days are held out to judge each model.
MIN_TRAIN_DAYS = 300


def mape(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Mean absolute percentage error: how far off, as a share of actual demand."""
    return float(np.mean(np.abs(forecast - actual) / actual))


def rmse(actual: np.ndarray, forecast: np.ndarray) -> float:
    return float(np.sqrt(np.mean((forecast - actual) ** 2)))


def split(known: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on all but the newest EVAL_DAYS labeled days; those judge the model."""
    first_eval = known["date"].max() - pd.Timedelta(days=EVAL_DAYS - 1)
    return known[known["date"] < first_eval], known[known["date"] >= first_eval]


@dataclass(frozen=True)
class Trained:
    run_id: str
    version: str
    as_of: date


def train(paths: Paths, as_of: date) -> Trained:
    """Train on every label known on the morning of `as_of`, except the newest EVAL_DAYS, and register a challenger."""
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        train_df, eval_df = split(features.labeled(con, as_of))
    if train_df["date"].nunique() < MIN_TRAIN_DAYS:
        raise SystemExit(f"only {train_df['date'].nunique()} labeled training days by {as_of}; need {MIN_TRAIN_DAYS}")

    model = HistGradientBoostingRegressor(random_state=0)
    model.fit(features.model_input(train_df), train_df[TARGET])
    forecast = model.predict(features.model_input(eval_df))
    actual = eval_df[TARGET].to_numpy()

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"hgb-{as_of}") as run:
        mlflow.log_params(
            {
                "model": "hist_gradient_boosting",
                "as_of": str(as_of),
                "train_start": str(train_df["date"].min().date()),
                "train_end": str(train_df["date"].max().date()),
                "eval_start": str(eval_df["date"].min().date()),
                "eval_end": str(eval_df["date"].max().date()),
            }
        )
        for name, frame in (("train", train_df), ("eval", eval_df)):
            mlflow.log_input(
                from_pandas(
                    features.model_input(frame).assign(**{TARGET: frame[TARGET]}),
                    source=str(paths.warehouse),
                    targets=TARGET,
                    name=name,
                ),
                context=name,
            )
        metrics = {"eval": forecast, "naive": eval_df["naive_forecast"].to_numpy()}
        operator = eval_df["operator_forecast"].to_numpy()
        if not np.isnan(operator).any():
            metrics["operator"] = operator
        for name, values in metrics.items():
            mlflow.log_metrics({f"{name}_mape": mape(actual, values), f"{name}_rmse": rmse(actual, values)})
        info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=infer_signature(features.model_input(eval_df), forecast),
            input_example=features.model_input(eval_df).head(3),
            # skops vets every type it loads; we trained this model ourselves, so trust its tree predictor.
            skops_trusted_types=["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
            # Naming the requirements skips MLflow's inference, which imports everything in a
            # subprocess and takes seconds per model: too slow for a replay that retrains dozens of times.
            pip_requirements=mlflow.sklearn.get_default_pip_requirements(include_skops=True),
        )
    version = str(info.registered_model_version)
    mlflow.MlflowClient().set_registered_model_alias(MODEL_NAME, CHALLENGER, version)
    return Trained(run.info.run_id, version, as_of)


def version_for(alias: str) -> str | None:
    try:
        return str(mlflow.MlflowClient().get_model_version_by_alias(MODEL_NAME, alias).version)
    except MlflowException:
        return None


_loaded: dict[str, PyFuncModel] = {}


def load(version: str) -> PyFuncModel:
    """Load a registered version once per process; replays forecast hundreds of days."""
    if version not in _loaded:
        _loaded[version] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    return _loaded[version]


def predict(version: str, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(load(version).predict(features.model_input(frame)), dtype=float)


@dataclass(frozen=True)
class Decision:
    promoted: bool
    reason: str
    challenger: str
    challenger_mape: float
    naive_mape: float
    champion_mape: float | None


def decide(mine: float, naive: float, theirs: float | None) -> tuple[bool, str]:
    """The gate, on MAPE (lower is better) for the challenger, the naive forecast, and the champion."""
    if mine >= naive:
        return False, f"MAPE {mine:.2%} does not beat naive's {naive:.2%}"
    if theirs is None:
        return True, f"MAPE {mine:.2%} beats naive's {naive:.2%}; no champion yet"
    if theirs >= naive:
        return True, f"champion's MAPE {theirs:.2%} no longer beats naive's {naive:.2%}"
    if mine <= theirs:
        return True, f"MAPE {mine:.2%} <= champion's {theirs:.2%}"
    return False, f"MAPE {mine:.2%} > champion's {theirs:.2%}"


def promote(paths: Paths, as_of: date) -> Decision:
    """Judge challenger, champion, and naive on the same newest EVAL_DAYS of labels; move the alias if earned.

    The gate: beat naive, and do at least as well as the champion (or the champion no longer beats
    naive itself).
    """
    challenger = version_for(CHALLENGER)
    if challenger is None:
        raise SystemExit("no challenger: run `mle bootstrap` first")
    champion = version_for(CHAMPION)
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        _, window = split(features.labeled(con, as_of))
    actual = window[TARGET].to_numpy()
    naive = mape(actual, window["naive_forecast"].to_numpy())
    mine = mape(actual, predict(challenger, window))
    theirs = mape(actual, predict(champion, window)) if champion and champion != challenger else None

    promoted, reason = decide(mine, naive, theirs)
    client = mlflow.MlflowClient()
    for key, value in {
        "gate_as_of": str(as_of),
        "gate_mape": f"{mine:.4f}",
        "gate_naive_mape": f"{naive:.4f}",
        "promotion": "promoted" if promoted else "rejected",
        "promotion_reason": reason,
    }.items():
        client.set_model_version_tag(MODEL_NAME, challenger, key, value)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION, challenger)
    return Decision(promoted, reason, challenger, mine, naive, theirs)


@cache
def trained_as_of(version: str) -> date:
    """The `as_of` date a version trained on; versions never change, so ask MLflow once."""
    client = mlflow.MlflowClient()
    run_id = client.get_model_version(MODEL_NAME, version).run_id
    assert run_id is not None, f"version {version} has no run"
    return date.fromisoformat(client.get_run(run_id).data.params["as_of"])


def age(version: str, as_of: date) -> timedelta:
    return as_of - trained_as_of(version)
