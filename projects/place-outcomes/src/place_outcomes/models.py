"""Outcomes and price models, scored with spatial cross-validation: whole counties are held out."""

from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import partial_dependence
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from place_outcomes.config import BASELINE_FACTOR, FACTORS, LABELS, STATES

FEATURES = list(FACTORS)
FOLDS = 5


def frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per ZIP: factors, labels, and the log of its latest home value."""
    df: pd.DataFrame = con.execute(
        """
        SELECT f.*, ln(v.value) AS log_value, v.county_name
        FROM zip_features f
        JOIN (SELECT zip, arg_max(value, month) AS value, any_value(county_name) AS county_name
              FROM zip_value GROUP BY zip) v USING (zip)
        """
    ).df()
    df["state"] = df["state_fips"].map(STATES)
    return df


def make_models() -> dict[str, Any]:
    return {
        "linear": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0)),
        "boosted": HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200, random_state=0),
    }


def spatial_folds(groups: pd.Series, n_splits: int = FOLDS) -> list[tuple[np.ndarray, np.ndarray]]:
    """Train and test index pairs where every county sits wholly in one test fold."""
    splits = GroupKFold(n_splits=min(n_splits, groups.nunique())).split(np.zeros(len(groups)), groups=groups)
    return [(train, test) for train, test in splits]


def out_of_fold(model: Any, x: pd.DataFrame, y: pd.Series, groups: pd.Series) -> np.ndarray:
    pred = np.full(len(y), np.nan)
    for train, test in spatial_folds(groups):
        fitted = clone(model).fit(x.iloc[train], y.iloc[train])
        pred[test] = fitted.predict(x.iloc[test])
    return pred


def evaluate(df: pd.DataFrame, target: str, baseline: str) -> dict[str, Any]:
    """Spatially cross-validated R² of each model and a baseline on one income column, with partial dependence."""
    data = df.dropna(subset=[target]).reset_index(drop=True)
    groups = data["county_fips"]
    y = data[target]
    scores = {
        "baseline": r2_score(
            y, out_of_fold(LinearRegression(), data[[baseline]].fillna(data[baseline].median()), y, groups)
        )
    }
    preds = {}
    for name, model in make_models().items():
        preds[name] = out_of_fold(model, data[FEATURES], y, groups)
        scores[name] = r2_score(y, preds[name])
    boosted = make_models()["boosted"].fit(data[FEATURES], y)
    pdp = {}
    for feature in FEATURES:
        result = partial_dependence(boosted, data[FEATURES], [feature], grid_resolution=5)
        pdp[feature] = list(zip(result["grid_values"][0].tolist(), result["average"][0].tolist(), strict=True))
    linear = make_models()["linear"].fit(data[FEATURES], y)
    coefficients = dict(zip(FEATURES, linear[-1].coef_.tolist(), strict=True))
    return {
        "n": len(data),
        "counties": int(groups.nunique()),
        "r2": scores,
        "adds_over_baseline": max(scores["linear"], scores["boosted"]) - scores["baseline"],
        "partial_dependence": pdp,
        "standardized_coefficients": coefficients,
        "_data": data.assign(oof=preds["boosted"]),
    }


def outcomes(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Question 1: adult income rank and incarceration rate against the parental income baseline."""
    return {label: evaluate(df, label, BASELINE_FACTOR) for label in LABELS}


def school_price(df: pd.DataFrame) -> dict[str, float]:
    """Question 2: percent change in home value for one standard deviation of school score, within each state."""
    out: dict[str, float] = {}
    for state, part in df.dropna(subset=["log_value"]).groupby("state"):
        x = part[FEATURES]
        x = x.fillna(x.median())
        z = (x - x.mean()) / x.std().replace(0, 1)
        fit = LinearRegression().fit(z, part["log_value"])
        out[str(state)] = float(np.expm1(fit.coef_[FEATURES.index("school_math")]))
    return out


def price(df: pd.DataFrame, extremes: int = 10) -> dict[str, Any]:
    """Question 2: a hedonic model of log home value, the school price per state, and the largest residuals."""
    result = evaluate(df, "log_value", "median_income")
    data: pd.DataFrame = result.pop("_data")
    data["residual"] = data["log_value"] - data["oof"]
    cols = ["zip", "state", "county_name", "log_value", "oof", "residual"]
    result["school_price_per_sd"] = school_price(df)
    result["above_prediction"] = data.nlargest(extremes, "residual")[cols]
    result["below_prediction"] = data.nsmallest(extremes, "residual")[cols]
    return result
