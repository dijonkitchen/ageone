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

# Area factors and outcomes (questions 1 and 2). Census and NCES files are public domain.
CENSUS_OPPORTUNITY = "https://www2.census.gov/ces/opportunity/"
TRACT_OUTCOMES_FILE = "tract_outcomes_simple.csv"  # Opportunity Atlas: adult outcomes by childhood tract.
TRACT_COVARIATES_FILE = "tract_covariates.csv"  # Opportunity Atlas: tract traits (2010 tracts).
ZCTA_TRACT_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_tract_rel_10.txt"
ZCTA_TRACT_FILE = "zcta_tract_rel_10.txt"  # 2010 ZCTA-to-tract parts with population, matching the Atlas tracts.
GRF_URL = "https://nces.ed.gov/programs/edge/data/GRF24.zip"
GRF_MEMBER = "GRF24/grf24_lea_zcta5ce20.sas7bdat"
LEA_ZCTA_FILE = "lea_zcta.csv"  # NCES school district (LEA) to ZCTA land-area overlaps, cut to STATES.
# Stanford Education Data Archive: downloading means accepting its data use agreement
# (edopportunity.org/trends/data), which bars republishing the files in full or in part.
SEDA_URL = "https://stacks.stanford.edu/file/np279jm6134/seda_admindist_poolsub_cs_2025.2.csv"
SEDA_FILE = "seda_admindist_poolsub_cs_2025.2.csv"
STATE_FIPS = {"CA": "06", "NJ": "34"}

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
