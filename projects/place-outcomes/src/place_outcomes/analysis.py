"""Questions 1 and 2: which place factors line up with adult outcomes, and with home prices.

Both are descriptive. Families choose where to live, so a factor that predicts an outcome or a price
is not shown to cause it. Every score is cross-validated with whole counties held out, so a ZIP is
never predicted from its own neighbors in the training folds.
"""

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FOLDS = 5
# Factors a home seeker weighs, as model inputs. Race and ethnicity composition is deliberately left out.
FACTORS = ["achievement", "learning", "log_density", "log_jobs_highpay", "commute", "coll", "poor", "single_parent"]
BASELINE = ["log_med_hhinc", "ca"]  # Area income and state: the bar the factors must add to.
PRICE_CONTROLS = ["log_med_hhinc", "log_density", "log_jobs_highpay", "commute", "coll", "poor"]
LABELS = {
    "achievement": "School achievement (grades 3-8)",
    "learning": "School learning rate",
    "log_density": "Population density (log)",
    "log_jobs_highpay": "High-paying jobs within 5 miles (log)",
    "commute": "Mean commute time",
    "coll": "Adults with a college degree",
    "poor": "Share in poverty",
    "single_parent": "Single-parent households",
    "kfr": "Adult income rank, children of 25th percentile parents",
    "log_med_hhinc": "Median household income (log)",
    "ca": "California (vs New Jersey)",
}


def frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """ZIPs with every input and both labels, with the transforms the models use."""
    df = con.execute("SELECT * FROM zip_factors ORDER BY zip").df()
    df["log_density"] = np.log1p(df["density"])
    df["log_jobs_highpay"] = np.log1p(df["jobs_highpay"])
    df["log_med_hhinc"] = np.log(df["med_hhinc"])
    df["ca"] = (df["state"] == "CA").astype(float)
    needed = [*FACTORS, *BASELINE, "kfr", "log_value", "county"]
    return df.dropna(subset=needed).reset_index(drop=True)


def folds(df: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    """County-grouped folds: every ZIP of a county lands in the same test fold."""
    n = min(FOLDS, df["county"].nunique())
    return list(GroupKFold(n_splits=n).split(df, groups=df["county"]))


def linear() -> object:
    return make_pipeline(StandardScaler(), LinearRegression())


def boosted() -> object:
    return HistGradientBoostingRegressor(random_state=0, max_iter=200)


def cv_predict(df: pd.DataFrame, features: list[str], target: str, make: object) -> np.ndarray:
    out = np.empty(len(df))
    for train, test in folds(df):
        model = make()  # type: ignore[operator]
        model.fit(df.loc[train, features], df.loc[train, target])
        out[test] = model.predict(df.loc[test, features])
    return out


def cv_r2(df: pd.DataFrame, features: list[str], target: str, make: object) -> float:
    return float(r2_score(df[target], cv_predict(df, features, target, make)))


def by_state(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {str(s): g.reset_index(drop=True) for s, g in df.groupby("state")}


def _r2s(df: pd.DataFrame, features: list[str], target: str) -> tuple[float, float, float]:
    """Cross-validated R² of the baseline, the linear model, and the boosted model."""
    return (
        cv_r2(df, BASELINE, target, linear),
        cv_r2(df, features, target, linear),
        cv_r2(df, features, target, boosted),
    )


@dataclass(frozen=True)
class Scores:
    target: str
    zips: int
    counties: int
    baseline_r2: float
    linear_r2: float
    boosted_r2: float
    adds: dict[str, float]  # Each factor: cross-validated R² lost when the linear model drops it.
    coefficients: dict[str, float]  # Standardized linear coefficients on the full data.
    states: dict[str, tuple[float, float, float]]  # Per state with 2+ counties: baseline, linear, boosted R².


def score(df: pd.DataFrame, features: list[str], target: str) -> Scores:
    full = cv_r2(df, features, target, linear)
    adds = {f: full - cv_r2(df, [g for g in features if g != f], target, linear) for f in features}
    fitted = linear()
    fitted.fit(df[features], df[target])  # type: ignore[attr-defined]
    coefs = dict(zip(features, fitted[-1].coef_, strict=True))  # type: ignore[index]
    return Scores(
        target=target,
        zips=len(df),
        counties=int(df["county"].nunique()),
        baseline_r2=cv_r2(df, BASELINE, target, linear),
        linear_r2=full,
        boosted_r2=cv_r2(df, features, target, boosted),
        adds=adds,
        coefficients={k: float(v) for k, v in coefs.items()},
        states={state: _r2s(g, features, target) for state, g in by_state(df).items() if g["county"].nunique() > 1},
    )


def outcomes(df: pd.DataFrame) -> Scores:
    """Question 1: adult income rank of children from 25th percentile families, from today's factors."""
    return score(df, [*FACTORS, *BASELINE], "kfr")


@dataclass(frozen=True)
class Price:
    scores: Scores
    school_premium: dict[str, float]  # Per state: home value change per SD of school achievement, with controls.
    school_premium_raw: dict[str, float]  # The same without controls.
    residuals: pd.DataFrame  # Every ZIP: actual and cross-validated predicted log value, and their gap.


def premium(df: pd.DataFrame, controls: list[str]) -> float:
    """exp(coefficient) - 1 on standardized achievement: the value difference for one SD better schools."""
    z = (df["achievement"] - df["achievement"].mean()) / df["achievement"].std()
    x = df[controls].assign(z=z)
    coef = LinearRegression().fit(x, df["log_value"]).coef_[-1]
    return float(np.expm1(coef))


def price(df: pd.DataFrame) -> Price:
    """Question 2: what the factors explain of home value, and the school premium in each state."""
    features = [*FACTORS, *BASELINE, "kfr"]
    predicted = cv_predict(df, features, "log_value", boosted)
    residuals = df[["zip", "state", "county", "log_value", "achievement", "kfr"]].assign(
        predicted=predicted, gap=df["log_value"] - predicted
    )
    states = by_state(df)
    return Price(
        scores=score(df, features, "log_value"),
        school_premium={s: premium(g, PRICE_CONTROLS) for s, g in states.items()},
        school_premium_raw={s: premium(g, []) for s, g in states.items()},
        residuals=residuals.sort_values("gap").reset_index(drop=True),
    )
