"""Train a volatility model, track it in MLflow, and promote it only when it earns it.

The model is HAR (heterogeneous autoregressive, Corsi 2009): a linear regression of log future
volatility on log volatility over the last day, week, and month, plus the VIX. The bar it must clear
is the baseline every forecaster is judged against: next week looks like last week (`rv_5d`).
"""

from dataclasses import dataclass
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
from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from mle_lab import features
from mle_lab.config import CHALLENGER, CHAMPION, EXPERIMENT, FEATURES, MODEL_NAME, TARGET, Paths

EVAL_DAYS = 63  # The newest quarter of labeled days is held out to judge each model.
MIN_TRAIN_DAYS = 250
EPS = 1e-8


def qlike(realized: np.ndarray, forecast: np.ndarray) -> float:
    """The standard loss for variance forecasts: it punishes calling a storm calm more than the reverse."""
    ratio = np.maximum(realized, EPS) ** 2 / np.maximum(forecast, EPS) ** 2
    return float(np.mean(ratio - np.log(ratio) - 1))


def rmse(realized: np.ndarray, forecast: np.ndarray) -> float:
    return float(np.sqrt(np.mean((realized - forecast) ** 2)))


def pipeline() -> TransformedTargetRegressor:
    log = FunctionTransformer(np.log)
    return TransformedTargetRegressor(
        regressor=Pipeline([("log", log), ("linear", LinearRegression())]), func=np.log, inverse_func=np.exp
    )


def model_input(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[FEATURES].clip(lower=EPS)


@dataclass(frozen=True)
class Trained:
    run_id: str
    version: str
    as_of: str


def train(paths: Paths, as_of: str) -> Trained:
    """Train on every label known by `as_of`, except the newest EVAL_DAYS, and register a challenger."""
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        day = features.day_of(con, as_of)
        known = features.labeled(con, day)
    train_df, eval_df = known.iloc[:-EVAL_DAYS], known.iloc[-EVAL_DAYS:]
    if len(train_df) < MIN_TRAIN_DAYS:
        raise SystemExit(f"only {len(train_df)} labeled training days by {as_of}; need {MIN_TRAIN_DAYS}")

    model = pipeline().fit(model_input(train_df), train_df[TARGET])
    forecast = model.predict(model_input(eval_df))
    realized = eval_df[TARGET].to_numpy()

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"har-{as_of}") as run:
        mlflow.log_params(
            {
                "model": "har",
                "as_of": as_of,
                "train_start": str(train_df["date"].iloc[0].date()),
                "train_end": str(train_df["date"].iloc[-1].date()),
                "eval_start": str(eval_df["date"].iloc[0].date()),
                "eval_end": str(eval_df["date"].iloc[-1].date()),
            }
        )
        for name, frame in (("train", train_df), ("eval", eval_df)):
            mlflow.log_input(
                from_pandas(frame[[*FEATURES, TARGET]], source=str(paths.warehouse), targets=TARGET, name=name),
                context=name,
            )
        mlflow.log_metrics(
            {
                "eval_qlike": qlike(realized, forecast),
                "eval_rmse": rmse(realized, forecast),
                "baseline_qlike": qlike(realized, eval_df["rv_5d"].to_numpy()),
                "baseline_rmse": rmse(realized, eval_df["rv_5d"].to_numpy()),
            }
        )
        linear = model.regressor_.named_steps["linear"]
        mlflow.log_params({f"coef_{f}": round(float(c), 4) for f, c in zip(FEATURES, linear.coef_, strict=True)})
        info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=infer_signature(model_input(eval_df), forecast),
            input_example=model_input(eval_df).head(3),
            # skops vets every type it loads; we wrote this pipeline, so trust numpy's log and exp.
            skops_trusted_types=["numpy.log", "numpy.exp"],
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
    """Load a registered version once per process; replays score thousands of days."""
    if version not in _loaded:
        _loaded[version] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    return _loaded[version]


def predict(version: str, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(load(version).predict(model_input(frame)), dtype=float)


@dataclass(frozen=True)
class Decision:
    promoted: bool
    reason: str
    challenger: str
    challenger_qlike: float
    baseline_qlike: float
    champion_qlike: float | None


def decide(mine: float, base: float, theirs: float | None) -> tuple[bool, str]:
    """The gate, on QLIKE (lower is better) for the challenger, the baseline, and the champion."""
    if mine >= base:
        return False, f"QLIKE {mine:.3f} does not beat the baseline's {base:.3f}"
    if theirs is None:
        return True, f"QLIKE {mine:.3f} beats the baseline's {base:.3f}; no champion yet"
    if theirs >= base:
        return True, f"champion's QLIKE {theirs:.3f} no longer beats the baseline's {base:.3f}"
    if mine <= theirs:
        return True, f"QLIKE {mine:.3f} <= champion's {theirs:.3f}"
    return False, f"QLIKE {mine:.3f} > champion's {theirs:.3f}"


def promote(paths: Paths, as_of: str) -> Decision:
    """Judge challenger, champion, and baseline on the same newest EVAL_DAYS labels; move the alias if earned.

    The gate: beat the baseline, and do at least as well as the champion (or the champion no longer
    beats the baseline itself).
    """
    challenger = version_for(CHALLENGER)
    if challenger is None:
        raise SystemExit("no challenger: run `mle train` first")
    champion = version_for(CHAMPION)
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        window = features.labeled(con, features.day_of(con, as_of)).iloc[-EVAL_DAYS:]
    realized = window[TARGET].to_numpy()
    base = qlike(realized, window["rv_5d"].to_numpy())
    mine = qlike(realized, predict(challenger, window))
    theirs = qlike(realized, predict(champion, window)) if champion and champion != challenger else None

    promoted, reason = decide(mine, base, theirs)
    client = mlflow.MlflowClient()
    for key, value in {
        "gate_as_of": as_of,
        "gate_qlike": f"{mine:.4f}",
        "gate_baseline_qlike": f"{base:.4f}",
        "promotion": "promoted" if promoted else "rejected",
        "promotion_reason": reason,
    }.items():
        client.set_model_version_tag(MODEL_NAME, challenger, key, value)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION, challenger)
    return Decision(promoted, reason, challenger, mine, base, theirs)


@cache
def trained_as_of(version: str) -> str:
    """The `as_of` date a version trained on; versions never change, so ask MLflow once."""
    client = mlflow.MlflowClient()
    run_id = client.get_model_version(MODEL_NAME, version).run_id
    assert run_id is not None, f"version {version} has no run"
    return str(client.get_run(run_id).data.params["as_of"])
