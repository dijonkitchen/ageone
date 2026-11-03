import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from place_outcomes import data, factors, features
from place_outcomes.config import Paths

# Real Zillow Home Value Index rows for the 20 largest ZIPs in each of California and New Jersey,
# January 2000 through September 2026, in Zillow's own file layout. Data provided by Zillow.
DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "Zip_zhvi_sample.csv.gz"
# Area factor files for the same ZIPs; see data/README.md (the SEDA scores are made up).
FACTOR_FILES = [
    "zcta_tract_rel_10.txt",
    "tract_outcomes_simple.csv",
    "tract_covariates.csv",
    "lea_zcta.csv",
    "seda_admindist_poolsub_cs_2025.2.csv",
]


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Paths]:
    """A fresh warehouse with features built, and a fresh MLflow store, in tmp_path."""
    paths = Paths(tmp_path / "data")
    paths.raw.mkdir(parents=True)
    shutil.copy(FIXTURE, paths.raw / FIXTURE.name.replace("_sample", ""))
    with duckdb.connect(str(paths.warehouse)) as con:
        data.load(con, paths.raw)
        features.build(con)
    monkeypatch.chdir(tmp_path)
    # MLflow reads this on every call, so each test gets its own tracking store and registry.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    yield paths


@pytest.fixture
def places(lab: Paths) -> Paths:
    """The lab warehouse plus area factors by ZIP."""
    for name in FACTOR_FILES:
        shutil.copy(DATA / name, lab.raw / name)
    with duckdb.connect(str(lab.warehouse)) as con:
        factors.load(con, lab.raw)
        factors.build(con)
    return lab
