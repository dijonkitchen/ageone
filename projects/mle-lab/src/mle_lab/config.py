"""Names and settings every stage shares."""

from dataclasses import dataclass
from pathlib import Path

# FRED series ids: the S&P 500 close and the VIX close. Both are copyrighted, so they are fetched
# at run time into the git-ignored data folder and never committed.
SERIES = {"sp500": "SP500", "vix": "VIXCLS"}
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

HORIZON = 5  # Trading days ahead we forecast, and so how long each label takes to arrive.
TRADING_DAYS = 252
FEATURES = ["rv_1d", "rv_5d", "rv_21d", "vix"]
TARGET = "target_rv_5d"

MODEL_NAME = "sp500-vol"
EXPERIMENT = "sp500-vol"
CHAMPION = "champion"
CHALLENGER = "challenger"


@dataclass(frozen=True)
class Paths:
    """The lab's files, all under one data folder (git-ignored)."""

    data_dir: Path

    @property
    def raw(self) -> Path:
        return self.data_dir / "raw"

    @property
    def warehouse(self) -> Path:
        return self.data_dir / "warehouse.duckdb"
