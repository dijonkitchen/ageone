"""Names and settings every stage shares."""

from dataclasses import dataclass
from pathlib import Path

# Zillow Home Value Index by ZIP: all homes, middle third of values, smoothed and seasonally adjusted, monthly.
# Free for public use with attribution: "Data provided by Zillow" (zillowgroup.com/developers/api/public-data/).
ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
ZHVI_FILE = "Zip_zhvi.csv"
STATES = ("CA", "NJ")

HORIZON = 12  # Months ahead each forecast looks: the log change in home value over the next year.
EVAL_MONTHS = 12  # The newest origin months with known labels judge each model.

FEATURES = ["r1", "r3", "r6", "r12", "r24", "r60", "vol12", "rel_level", "state_r1", "state_r12", "metro_r12", "moy"]
CATEGORICAL = ["state"]
TARGET = "y"

MODEL_NAME = "zip-home-value"
EXPERIMENT = "zip-home-value"
CHAMPION = "champion"
CHALLENGER = "challenger"


@dataclass(frozen=True)
class Paths:
    """The project's files, all under one data folder (git-ignored)."""

    data_dir: Path

    @property
    def raw(self) -> Path:
        return self.data_dir / "raw"

    @property
    def manifest(self) -> Path:
        return self.raw / "manifest.json"

    @property
    def warehouse(self) -> Path:
        return self.data_dir / "warehouse.duckdb"
