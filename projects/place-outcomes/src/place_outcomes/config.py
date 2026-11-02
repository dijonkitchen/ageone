"""Sources, states, factor lists, and where files live."""

from dataclasses import dataclass
from pathlib import Path

STATES = {"06": "CA", "34": "NJ"}

ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
ATLAS_OUTCOMES_URL = "https://www2.census.gov/ces/opportunity/tract_outcomes_simple.csv"
ATLAS_COVARIATES_URL = "https://www2.census.gov/ces/opportunity/tract_covariates.csv"
ZCTA_TRACT_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_tract_rel_10.txt"

SOURCES = {
    "zhvi.csv": ZHVI_URL,
    "atlas_outcomes.csv": ATLAS_OUTCOMES_URL,
    "atlas_covariates.csv": ATLAS_COVARIATES_URL,
    "zcta_tract_rel_10.txt": ZCTA_TRACT_URL,
}

# Factors that are measured around 2010 to 2016 and describe a place today. Race and ethnicity shares are
# deliberately absent: they never enter a model or a ranking (fair housing).
FACTORS = {
    "school_math": "gsmn_math_g3_2013",  # Atlas covariate: average 3rd grade math score, 2013
    "median_income": "med_hhinc2016",
    "poverty_share": "poor_share2010",
    "college_share": "frac_coll_plus2010",
    "single_parent_share": "singleparent_share2010",
    "foreign_share": "foreign_share2010",
    "short_commute_share": "traveltime15_2010",
    "pop_density": "popdensity2010",
    "job_density": "job_density_2013",
    "jobs_within_5mi": "jobs_total_5mi_2015",
    "job_growth": "ann_avg_job_growth_2004_2013",
    "rent_two_bed": "rent_twobed2015",
}
# Parental income stand-in for the outcomes baseline: the tract's 1990 median household income.
BASELINE_FACTOR = "median_income_1990"
BASELINE_COLUMN = "med_hhinc1990"
LABELS = {"adult_income_rank": "kfr_pooled_pooled_p25", "incarceration_rate": "jail_pooled_pooled_p25"}
HORIZON = 12  # months ahead the forecast looks


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def warehouse(self) -> Path:
        return self.root / "warehouse.duckdb"

    @property
    def mlflow(self) -> str:
        return f"sqlite:///{self.root / 'mlflow.db'}"

    @property
    def manifest(self) -> Path:
        return self.raw / "manifest.json"

    @property
    def report(self) -> Path:
        return self.root / "report.html"


def default_paths() -> Paths:
    return Paths(Path("data"))
