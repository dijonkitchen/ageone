import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from mle_lab import data, features
from mle_lab.config import Paths

# Real ERCOT hours from EIA-930 (public domain; Source: U.S. Energy Information Administration),
# 2024-01-01 through 2025-04-30 local time, cut to the columns the lab reads.
FIXTURE = Path(__file__).parent / "data"


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Paths]:
    """A fresh warehouse with features built, and a fresh MLflow store, in tmp_path."""
    paths = Paths(tmp_path / "data")
    shutil.copytree(FIXTURE, paths.raw)
    with duckdb.connect(str(paths.warehouse)) as con:
        data.load(con, paths.raw)
        features.build(con)
    monkeypatch.chdir(tmp_path)
    # MLflow reads this on every call, so each test gets its own tracking store and registry.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    yield paths
