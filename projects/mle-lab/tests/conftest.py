import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from mle_lab import data, features
from mle_lab.config import Paths

CUSTOMERS = 1500


@pytest.fixture(scope="session")
def raw(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generated once per test session; each test gets its own copy."""
    out = tmp_path_factory.mktemp("raw")
    data.generate(out, customers=CUSTOMERS)
    return out


@pytest.fixture
def lab(raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Paths]:
    """A fresh warehouse with features built, and a fresh MLflow store, in tmp_path."""
    paths = Paths(tmp_path / "data")
    shutil.copytree(raw, paths.raw)
    with duckdb.connect(str(paths.warehouse)) as con:
        features.build(con, paths.raw)
    monkeypatch.chdir(tmp_path)
    # MLflow reads this on every call, so each test gets its own tracking store and registry.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    yield paths
