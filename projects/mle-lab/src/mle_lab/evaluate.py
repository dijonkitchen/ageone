"""Evals for a registered model on one labeled month: metrics, slices, and the gates a champion must pass.

Every evaluation lands in the warehouse's `evaluations` table and in MLflow, so the history of how
each version did on each month is one query away.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import duckdb
import mlflow
import mlflow.pyfunc
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from mle_lab import features
from mle_lab.config import EVAL_EXPERIMENT, LABEL, MODEL_NAME, Paths
from mle_lab.data import month_start

# Gates a model must pass on the newest labeled month to become (or stay) champion.
MIN_AUC = 0.70
MAX_CALIBRATION_GAP = 0.03  # Mean predicted churn vs the actual rate.
MIN_SLICE_AUC = 0.60
MIN_SLICE_ROWS = 100
MIN_SLICE_CHURNERS = 5
SLICE_BY = "plan"


def scores(y_true: pd.Series, p: pd.Series) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y_true, p)),
        "pr_auc": float(average_precision_score(y_true, p)),
        "log_loss": float(log_loss(y_true, p, labels=[False, True])),
        "brier": float(brier_score_loss(y_true, p)),
        "calibration_gap": float(abs(p.mean() - y_true.mean())),
    }


@dataclass
class Evaluation:
    month: int
    model_version: str
    rows: int
    metrics: dict[str, float]
    slices: dict[str, float]
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate_frame(frame: pd.DataFrame, p: pd.Series, month: int, version: str) -> Evaluation:
    y = frame[LABEL]
    metrics = scores(y, p)
    slices = {}
    for value, rows in frame.groupby(SLICE_BY):
        if len(rows) >= MIN_SLICE_ROWS and rows[LABEL].sum() >= MIN_SLICE_CHURNERS:
            slices[f"{SLICE_BY}_{value}"] = float(roc_auc_score(rows[LABEL], p[rows.index]))

    failures = []
    if metrics["roc_auc"] < MIN_AUC:
        failures.append(f"ROC AUC {metrics['roc_auc']:.3f} < {MIN_AUC}")
    if metrics["calibration_gap"] > MAX_CALIBRATION_GAP:
        failures.append(f"calibration gap {metrics['calibration_gap']:.3f} > {MAX_CALIBRATION_GAP}")
    failures += [f"{name} ROC AUC {auc:.3f} < {MIN_SLICE_AUC}" for name, auc in slices.items() if auc < MIN_SLICE_AUC]
    return Evaluation(month, version, len(frame), metrics, slices, failures)


def evaluate(paths: Paths, version: str, month: int) -> Evaluation:
    """Score `month` with model `version` and judge it against that month's labels."""
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        frame = features.load(con, [month_start(month).isoformat()])
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    p = pd.Series(model.predict(features.model_input(frame))[:, 1], index=frame.index)
    return evaluate_frame(frame, p, month, version)


def record(paths: Paths, ev: Evaluation, role: str) -> None:
    """Keep an evaluation in DuckDB and MLflow; `role` says why it ran (champion, challenger)."""
    snapshot = month_start(ev.month).isoformat()
    with duckdb.connect(str(paths.warehouse)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS evaluations (snapshot_date DATE, model_version VARCHAR, role VARCHAR, "
            "rows BIGINT, roc_auc DOUBLE, pr_auc DOUBLE, log_loss DOUBLE, brier DOUBLE, calibration_gap DOUBLE, "
            "slices JSON, failures VARCHAR[], passed BOOLEAN, evaluated_at TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO evaluations VALUES ($s::DATE, $v, $role, $rows, $roc_auc, $pr_auc, $log_loss, $brier, "
            "$calibration_gap, $slices::JSON, $failures, $passed, $at)",
            {
                "s": snapshot,
                "v": ev.model_version,
                "role": role,
                "rows": ev.rows,
                **ev.metrics,
                "slices": pd.Series(ev.slices).to_json(),
                "failures": ev.failures,
                "passed": ev.passed,
                "at": datetime.now(UTC).replace(tzinfo=None),
            },
        )
    mlflow.set_experiment(EVAL_EXPERIMENT)
    with mlflow.start_run(run_name=f"v{ev.model_version}-{snapshot}"):
        mlflow.set_tags({"model_version": ev.model_version, "month": snapshot, "role": role, "passed": str(ev.passed)})
        mlflow.log_metrics(ev.metrics | {f"auc_{k}": v for k, v in ev.slices.items()})
        mlflow.log_dict(asdict(ev), "evaluation.json")
