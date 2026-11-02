"""The forecast loop: 12-month home value change per ZIP, retrained monthly behind an eval gate.

Months are integers (the index into the sorted month list). "As of month A" means A is the latest published
month: features at t use only months up to t, and a label for t (the change from t to t + 12) exists only
once t + 12 <= A.
"""

import os
from dataclasses import dataclass
from typing import Any

import duckdb
import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from sklearn.ensemble import HistGradientBoostingRegressor

from place_outcomes.config import FACTORS, HORIZON, Paths
from place_outcomes.features import _run

MODEL_NAME = "place-outcomes-forecast"
TRAIN_MONTHS = 60  # how far back training rows reach
TRAIN_STRIDE = 3  # every third month, since neighboring months are nearly the same row
GATE_MONTHS = 12
LAGS = (3, 6, 12)
PRICE_FEATURES = ["r3", "r6", "r12", "r12_prev", "accel", "log_value"]
# The model learns how a ZIP differs from the market (the median ZIP) and gets only the cross-sectional
# deviations. The market's own 12-month change is a regime no ZIP feature can predict, so it is forecast
# as MARKET_WEIGHT times its trailing change: halfway between no-change and momentum. The weight was picked from
# 0, 0.5, and 1 by looking at replay errors (see the README), so replay scores for it are in-sample.
MARKET_WEIGHT = 0.5
FEATURES = [*(f"{c}_d" for c in PRICE_FEATURES), *FACTORS, "is_ca"]


@dataclass(frozen=True)
class Panel:
    log_value: pd.DataFrame  # rows are months in order, columns are ZIPs
    statics: pd.DataFrame  # indexed by ZIP: factors and `is_ca`

    @property
    def months(self) -> list[str]:
        return [str(m) for m in self.log_value.index]


def load_panel(con: duckdb.DuckDBPyConnection) -> Panel:
    values: pd.DataFrame = con.execute("SELECT zip, month, ln(value) AS v FROM zip_value").df()
    wide = values.pivot(index="month", columns="zip", values="v").sort_index()
    wide.index = pd.Index([d.strftime("%Y-%m") for d in wide.index], name="month")
    statics: pd.DataFrame = con.execute(
        f"SELECT zip, {', '.join(FACTORS)}, (state_fips = '06')::INT AS is_ca FROM zip_features"
    ).df()
    statics = statics.set_index("zip").reindex(wide.columns)
    # The ZIP's state when no tract feeds it: read from the value table.
    states = con.execute("SELECT DISTINCT zip, state FROM zip_value").df().set_index("zip")["state"]
    statics["is_ca"] = statics["is_ca"].fillna((states.reindex(wide.columns) == "CA").astype(float))
    return Panel(wide, statics)


def features_at(panel: Panel, t: int) -> pd.DataFrame:
    """Features for every ZIP as of month index `t`, from months 0..t only."""
    lv = panel.log_value.iloc[: t + 1]
    out = pd.DataFrame(index=lv.columns)
    for lag in LAGS:
        out[f"r{lag}"] = lv.iloc[t] - lv.iloc[t - lag] if t >= lag else np.nan
    out["r12_prev"] = lv.iloc[t - 12] - lv.iloc[t - 24] if t >= 24 else np.nan
    out["accel"] = out["r3"] * 4 - out["r12"]
    out["log_value"] = lv.iloc[t]
    for col in PRICE_FEATURES:
        out[f"{col}_d"] = out[col] - out[col].median()
    out["mkt_r12"] = out["r12"].median()
    return out.join(panel.statics[[*FACTORS, "is_ca"]])


def label_at(panel: Panel, t: int) -> pd.Series:
    """The realised change from month t to t + HORIZON; only known once month t + HORIZON is published."""
    lv = panel.log_value
    return lv.iloc[t + HORIZON] - lv.iloc[t]


def training_rows(panel: Panel, last_t: int) -> tuple[pd.DataFrame, pd.Series]:
    """Rows for months up to `last_t`, which must itself have a label by the as-of month.
    The label is each ZIP's change minus that month's median change."""
    xs, ys = [], []
    for t in range(max(24, last_t - TRAIN_MONTHS), last_t + 1, TRAIN_STRIDE):
        x, y = features_at(panel, t), label_at(panel, t)
        keep = y.notna() & x["r12"].notna()
        xs.append(x[keep])
        ys.append(y[keep] - y[keep].median())
    return pd.concat(xs), pd.concat(ys)


def new_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="absolute_error", max_depth=4, learning_rate=0.05, max_iter=150, random_state=0
    )


@dataclass(frozen=True)
class GateResult:
    promote: bool
    reason: str


def gate(challenger: float, no_change: float, momentum: float, champion: float | None) -> GateResult:
    """Promote only if the challenger beats both baselines on MAE and does at least as well as the champion."""
    if challenger >= no_change:
        return GateResult(False, f"not better than no-change ({challenger:.4f} >= {no_change:.4f})")
    if challenger >= momentum:
        return GateResult(False, f"not better than momentum ({challenger:.4f} >= {momentum:.4f})")
    if champion is not None and challenger > champion:
        return GateResult(False, f"worse than the champion ({challenger:.4f} > {champion:.4f})")
    return GateResult(True, "beats no-change and momentum" + ("" if champion is None else " and the champion"))


def gate_data(panel: Panel, as_of: int) -> tuple[pd.DataFrame, pd.Series]:
    """The newest GATE_MONTHS of matured labels: months whose label arrived in the last GATE_MONTHS months."""
    first, last = as_of - HORIZON - GATE_MONTHS + 1, as_of - HORIZON
    xs, ys = [], []
    for t in range(first, last + 1):
        x, y = features_at(panel, t), label_at(panel, t)
        keep = y.notna() & x["r12"].notna()
        xs.append(x[keep])
        ys.append(y[keep])
    return pd.concat(xs), pd.concat(ys)


def predict(model: Any, x: pd.DataFrame) -> np.ndarray:
    """A ZIP's forecast: the model's deviation from the market plus the market's shrunk momentum."""
    return np.asarray(model.predict(x[FEATURES])) + MARKET_WEIGHT * x["mkt_r12"].to_numpy()


def mae(pred: Any, truth: pd.Series) -> float:
    return float(np.mean(np.abs(np.asarray(pred) - truth.to_numpy())))


def setup(paths: Paths) -> MlflowClient:
    # MLflow would otherwise shell out to uv to snapshot this project's lockfile for every model it logs.
    os.environ.setdefault("MLFLOW_UV_AUTO_DETECT", "false")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    paths.root.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(paths.mlflow)
    mlflow.set_registry_uri(paths.mlflow)
    mlflow.set_experiment("place-outcomes-forecast")
    return MlflowClient()


def champion_model(client: MlflowClient) -> tuple[Any, str] | None:
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except mlflow.exceptions.MlflowException:
        return None
    return mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion"), str(version.version)


def step(panel: Panel, as_of: int, client: MlflowClient, digests: dict[str, str] | None = None) -> dict[str, Any]:
    """One monthly run: train a challenger on rows whose labels matured before the gate window, score it on the
    gate window against both baselines and the champion, log to MLflow, and promote if the gate says so."""
    month = panel.months[as_of]
    x, y = training_rows(panel, as_of - HORIZON - GATE_MONTHS)
    gx, gy = gate_data(panel, as_of)
    model = new_model().fit(x[FEATURES], y)
    challenger_mae = mae(predict(model, gx), gy)
    no_change_mae = mae(np.zeros(len(gy)), gy)
    momentum_mae = mae(gx["r12"], gy)
    champion = champion_model(client)
    champion_mae = mae(predict(champion[0], gx), gy) if champion else None
    verdict = gate(challenger_mae, no_change_mae, momentum_mae, champion_mae)
    with mlflow.start_run(run_name=f"as-of-{month}"):
        mlflow.log_params({"as_of": month, "train_rows": len(y), "gate_rows": len(gy), **(digests or {})})
        mlflow.log_metrics(
            {
                "challenger_mae": challenger_mae,
                "no_change_mae": no_change_mae,
                "momentum_mae": momentum_mae,
                **({"champion_mae": champion_mae} if champion_mae is not None else {}),
            }
        )
        mlflow.set_tag("gate", verdict.reason)
        info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            # We trained this model ourselves, so trust its tree predictor.
            skops_trusted_types=["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
            # Naming the requirements skips MLflow's slow inference, which matters when a replay logs dozens of models.
            pip_requirements=["scikit-learn"],
        )
    version = str(info.registered_model_version)
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if verdict.promote:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)
    return {
        "as_of": month,
        "version": version,
        "promoted": verdict.promote,
        "reason": verdict.reason,
        "challenger_mae": challenger_mae,
        "no_change_mae": no_change_mae,
        "momentum_mae": momentum_mae,
        "champion_mae": champion_mae,
    }


def forecast_at(panel: Panel, as_of: int, client: MlflowClient) -> pd.DataFrame | None:
    """The champion's forecast of every ZIP's change over the next 12 months, with the momentum baseline.
    The truth column is filled only if that change has already happened."""
    champion = champion_model(client)
    if champion is None:
        return None
    x = features_at(panel, as_of)
    x = x[x["r12"].notna()]
    out = pd.DataFrame({"as_of": panel.months[as_of], "model": predict(champion[0], x), "momentum": x["r12"]})
    out["no_change"] = 0.0
    out["truth"] = label_at(panel, as_of).reindex(x.index) if as_of + HORIZON < len(panel.months) else np.nan
    out["version"] = champion[1]
    out.index.name = "zip"
    return out.reset_index()


def replay(
    con: duckdb.DuckDBPyConnection, panel: Panel, paths: Paths, start: str, end: str | None = None
) -> pd.DataFrame:
    """Bootstrap on `start` and step monthly to `end` (default: the newest month), recording each step and each
    forecast in the warehouse. Returns error by year of as-of month for the model and both baselines."""
    client = setup(paths)
    first = panel.months.index(start)
    last = panel.months.index(end) if end else len(panel.months) - 1
    steps, forecasts = [], []
    for as_of in range(first, last + 1):
        steps.append(step(panel, as_of, client))
        fc = forecast_at(panel, as_of, client)
        if fc is not None:
            forecasts.append(fc)
    steps_df = pd.DataFrame(steps)
    all_fc = (
        pd.concat(forecasts)
        if forecasts
        else pd.DataFrame(columns=["as_of", "zip", "model", "momentum", "no_change", "truth", "version"])
    )
    con.register("steps_df", steps_df)
    con.register("fc_df", all_fc)
    _run(con, "CREATE OR REPLACE TABLE steps AS SELECT * FROM steps_df")
    _run(con, "CREATE OR REPLACE TABLE forecasts AS SELECT * FROM fc_df")
    return summarize(all_fc)


def summarize(fc: pd.DataFrame) -> pd.DataFrame:
    """Mean absolute error by year, on forecasts whose 12 months have passed."""
    done = fc[fc["truth"].notna()].copy()
    done["year"] = done["as_of"].str[:4]
    for col in ("model", "momentum", "no_change"):
        done[f"{col}_ae"] = (done[col] - done["truth"]).abs()
    table = done.groupby("year")[["model_ae", "momentum_ae", "no_change_ae"]].mean()
    table.columns = pd.Index(["model", "momentum", "no_change"])
    total = done[["model_ae", "momentum_ae", "no_change_ae"]].mean()
    table.loc["all"] = total.to_numpy()
    return table
