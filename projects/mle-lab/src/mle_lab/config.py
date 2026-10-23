"""Names and settings every stage shares."""

from dataclasses import dataclass
from pathlib import Path

# EIA-930 six-month balance files: hourly demand and the operator's day-ahead forecast for every
# U.S. balancing authority. Public domain; cite "Source: U.S. Energy Information Administration".
EIA_URL = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_{year}_{half}.csv"
FIRST_YEAR = 2022
REGION = "ERCO"  # ERCOT, Texas.
TIMEZONE = "America/Chicago"  # The region's local time, which sets its days and hours.

FEATURES = ["hour", "dow", "doy", "holiday", "lag_2d", "lag_7d", "prev_mean", "prev_min", "prev_max"]
TARGET = "demand"

MODEL_NAME = "grid-demand"
EXPERIMENT = "grid-demand"
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
