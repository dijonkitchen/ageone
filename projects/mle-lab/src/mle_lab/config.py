"""Where each stage reads and writes, and the names they share."""

from dataclasses import dataclass
from pathlib import Path

MODEL_NAME = "churn"
TRAINING_EXPERIMENT = "churn-training"
MONITORING_EXPERIMENT = "churn-monitoring"
EVAL_EXPERIMENT = "churn-evals"
CHAMPION = "champion"
CHALLENGER = "challenger"

CATEGORICAL = ["plan", "region"]
NUMERIC = ["tenure_days", "logins_30d", "tickets_30d", "payment_failures_30d", "days_since_login"]
FEATURES = CATEGORICAL + NUMERIC
LABEL = "churned"


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

    @property
    def reports(self) -> Path:
        return self.data_dir / "reports"


@dataclass(frozen=True)
class Months:
    """How the generated months split: train, then a validation month, then production months.

    Month 0 is history only (it feeds month 1's features), so labels start at month 1.
    The first model trains on `train` and is judged on `validation`; each production month then
    runs one turn of the feedback loop.
    """

    total: int = 15
    validation: int = 8
    drift_from: int = 9

    @property
    def train(self) -> range:
        return range(1, self.validation)

    @property
    def production(self) -> range:
        return range(self.validation + 1, self.total)


DEFAULT_MONTHS = Months()
