import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb
import numpy as np
import pandas as pd

from mle_lab import data, features
from mle_lab.config import Paths

DAYS = 800


def write_fred_csvs(out: Path, days: int = DAYS, seed: int = 3) -> None:
    """FRED-shaped CSVs for an index whose returns follow GARCH(1,1), so volatility clusters like
    the real thing, and a VIX that tracks its volatility. Real S&P 500 data can't be committed."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=days)
    var = np.empty(days)
    ret = np.empty(days)
    var[0] = 1e-4
    for t in range(days):
        if t:
            var[t] = 2e-6 + 0.1 * ret[t - 1] ** 2 + 0.88 * var[t - 1]
        ret[t] = np.sqrt(var[t]) * rng.standard_normal()
    level = 3000 * np.exp(np.cumsum(ret))
    vix = 100 * np.sqrt(252 * var) * 1.15 * np.exp(0.05 * rng.standard_normal(days))
    out.mkdir(parents=True, exist_ok=True)
    sp = pd.DataFrame({"observation_date": dates.strftime("%Y-%m-%d"), "SP500": level.round(2).astype(str)})
    vx = pd.DataFrame({"observation_date": dates.strftime("%Y-%m-%d"), "VIXCLS": vix.round(2).astype(str)})
    sp.loc[10, "SP500"] = ""  # FRED leaves holidays empty.
    sp.to_csv(out / "SP500.csv", index=False)
    vx.to_csv(out / "VIXCLS.csv", index=False)


@pytest.fixture(scope="session")
def raw(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("raw")
    write_fred_csvs(out)
    return out


@pytest.fixture
def lab(raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Paths]:
    """A fresh warehouse with features built, and a fresh MLflow store, in tmp_path."""
    paths = Paths(tmp_path / "data")
    shutil.copytree(raw, paths.raw)
    with duckdb.connect(str(paths.warehouse)) as con:
        data.load(con, paths.raw)
        features.build(con)
    monkeypatch.chdir(tmp_path)
    # MLflow reads this on every call, so each test gets its own tracking store and registry.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    yield paths
