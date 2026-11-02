"""Train the 12-month home value model, track it in MLflow, and promote it only when it earns it.

The model is a histogram gradient boosted regressor on each ZIP's own momentum, volatility, and
price level, plus state and metro momentum. It must beat two baselines to ship: no change (home
values flat for a year) and momentum (the next year repeats the last). Neither baseline wins every
period: momentum misses turning points and no change misses trends.

Windows, for a model as of month T (labels known for origins up to T - HORIZON):

- eval: the newest EVAL_MONTHS labeled origins, T - HORIZON - EVAL_MONTHS + 1 through T - HORIZON;
- train: origins whose labels were known before the first eval origin, so through that origin minus
  HORIZON. This purge means no training label covers a month after any eval origin, so the eval
  error is what the model would have scored live.
"""

from dataclasses import dataclass
from datetime import date

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

from place_outcomes import features, months
from place_outcomes.config import CHALLENGER, CHAMPION, EVAL_MONTHS, EXPERIMENT, HORIZON, MODEL_NAME, TARGET, Paths

MIN_TRAIN_MONTHS = 24
EARLIEST = date(1990, 1, 1)


@dataclass(frozen=True)
class Windows:
    train_last: date
    eval_first: date
    eval_last: date


def windows(as_of: date) -> Windows:
    eval_last = months.add(as_of, -HORIZON)
    eval_first = months.add(eval_last, -(EVAL_MONTHS - 1))
    return Windows(months.add(eval_first, -HORIZON), eval_first, eval_last)


def mae(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Mean absolute error of the 12-month log change; 0.05 is about 5 percentage points."""
    return float(np.mean(np.abs(forecast - actual)))


def baselines(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    return {"nochange": np.zeros(len(frame)), "momentum": frame["r12"].to_numpy(dtype=float)}


def frames(paths: Paths, as_of: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    w = windows(as_of)
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        train_df = features.labeled(con, EARLIEST, w.train_last, as_of)
        eval_df = features.labeled(con, w.eval_first, w.eval_last, as_of)
    return train_df, eval_df


@dataclass(frozen=True)
class Trained:
    run_id: str
    version: str
    as_of: date


def train(paths: Paths, as_of: date) -> Trained:
    """Train on origins labeled before the eval window as of month `as_of`, and register a challenger."""
    train_df, eval_df = frames(paths, as_of)
    n_months = train_df["month"].nunique()
    if n_months < MIN_TRAIN_MONTHS or eval_df.empty:
        raise SystemExit(f"only {n_months} labeled training months as of {as_of}; need {MIN_TRAIN_MONTHS}")

    model = HistGradientBoostingRegressor(random_state=0)
    model.fit(features.model_input(train_df), train_df[TARGET])
    forecast = model.predict(features.model_input(eval_df))
    actual = eval_df[TARGET].to_numpy()

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"hgb-{as_of:%Y-%m}") as run:
        mlflow.log_params(
            {
                "model": "hist_gradient_boosting",
                "as_of": str(as_of),
                "horizon_months": HORIZON,
                "train_start": str(train_df["month"].min().date()),
                "train_end": str(train_df["month"].max().date()),
                "train_last_label": str(train_df["label_month"].max().date()),
                "eval_start": str(eval_df["month"].min().date()),
                "eval_end": str(eval_df["month"].max().date()),
                "zips": int(eval_df["zip"].nunique()),
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
        mlflow.log_metric("eval_mae", mae(actual, forecast))
        for name, values in baselines(eval_df).items():
            mlflow.log_metric(f"{name}_mae", mae(actual, values))
        info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=infer_signature(features.model_input(eval_df), forecast),
            input_example=features.model_input(eval_df).head(3),
            # skops vets every type it loads; we trained this model ourselves, so trust its tree predictor.
            skops_trusted_types=["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
            # Naming the requirements skips MLflow's slow inference of them, which a replay would pay per retrain.
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


# Versions never change, so loads and lookups are cached per tracking store and version.
_loaded: dict[tuple[str, str], PyFuncModel] = {}
_as_of: dict[tuple[str, str], date] = {}


def load(version: str) -> PyFuncModel:
    """Load a registered version once per process; a replay forecasts every month for years."""
    key = (mlflow.get_tracking_uri(), version)
    if key not in _loaded:
        _loaded[key] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    return _loaded[key]


def predict(version: str, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(load(version).predict(features.model_input(frame)), dtype=float)


@dataclass(frozen=True)
class Decision:
    promoted: bool
    reason: str
    challenger: str
    challenger_mae: float
    nochange_mae: float
    momentum_mae: float
    champion_mae: float | None


def decide(mine: float, nochange: float, momentum: float, theirs: float | None) -> tuple[bool, str]:
    """The gate, on MAE (lower is better): beat both baselines, and do at least as well as the champion
    unless the champion no longer beats both baselines itself."""
    bar = min(nochange, momentum)
    best = "no change" if nochange <= momentum else "momentum"
    if mine >= bar:
        return False, f"MAE {mine:.4f} does not beat {best}'s {bar:.4f}"
    if theirs is None:
        return True, f"MAE {mine:.4f} beats {best}'s {bar:.4f}; no champion yet"
    if theirs >= bar:
        return True, f"champion's MAE {theirs:.4f} no longer beats {best}'s {bar:.4f}"
    if mine <= theirs:
        return True, f"MAE {mine:.4f} <= champion's {theirs:.4f}"
    return False, f"MAE {mine:.4f} > champion's {theirs:.4f}"


def promote(paths: Paths, as_of: date) -> Decision:
    """Judge challenger, champion, and both baselines on the same eval window; move the alias if earned.

    A champion trained more recently than the challenger's eval window may have seen some of it,
    which only makes the champion harder to replace.
    """
    challenger = version_for(CHALLENGER)
    if challenger is None:
        raise SystemExit("no challenger: run `places bootstrap` first")
    champion = version_for(CHAMPION)
    _, window = frames(paths, as_of)
    actual = window[TARGET].to_numpy()
    base = {name: mae(actual, values) for name, values in baselines(window).items()}
    mine = mae(actual, predict(challenger, window))
    theirs = mae(actual, predict(champion, window)) if champion and champion != challenger else None

    promoted, reason = decide(mine, base["nochange"], base["momentum"], theirs)
    client = mlflow.MlflowClient()
    for key, value in {
        "gate_as_of": str(as_of),
        "gate_mae": f"{mine:.5f}",
        "gate_nochange_mae": f"{base['nochange']:.5f}",
        "gate_momentum_mae": f"{base['momentum']:.5f}",
        "promotion": "promoted" if promoted else "rejected",
        "promotion_reason": reason,
    }.items():
        client.set_model_version_tag(MODEL_NAME, challenger, key, value)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION, challenger)
    return Decision(promoted, reason, challenger, mine, base["nochange"], base["momentum"], theirs)


def trained_as_of(version: str) -> date:
    """The month a version was trained as of."""
    key = (mlflow.get_tracking_uri(), version)
    if key not in _as_of:
        client = mlflow.MlflowClient()
        run_id = client.get_model_version(MODEL_NAME, version).run_id
        assert run_id is not None, f"version {version} has no run"
        _as_of[key] = date.fromisoformat(client.get_run(run_id).data.params["as_of"])
    return _as_of[key]
