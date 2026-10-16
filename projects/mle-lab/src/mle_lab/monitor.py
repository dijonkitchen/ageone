"""Monitor a served month once its labels land: feature drift (PSI) against the champion's training
data, and how the predictions actually served did."""

import json
from dataclasses import asdict, dataclass, field

import duckdb
import mlflow
import numpy as np
import pandas as pd

from mle_lab import features
from mle_lab.config import CATEGORICAL, MODEL_NAME, MONITORING_EXPERIMENT, NUMERIC, Paths
from mle_lab.data import month_start
from mle_lab.evaluate import Evaluation, evaluate_frame, record
from mle_lab.train import trained_months

# Common rule of thumb: PSI under 0.1 is stable, 0.1-0.2 is worth a look, over 0.2 has shifted.
PSI_ALERT = 0.2
AUC_DROP_ALERT = 0.05
EPS = 1e-6


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Population stability index of `current` against `reference`.

    Categories, and numbers with few distinct values (like counts of rare events), compare value by
    value; other numbers compare across the reference's deciles.
    """
    if not pd.api.types.is_numeric_dtype(reference) or reference.nunique() <= bins:
        cats = sorted(set(reference) | set(current))
        ref = reference.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
        cur = current.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    else:
        edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
        ref = np.histogram(reference, edges)[0] / len(reference)
        cur = np.histogram(current, edges)[0] / len(current)
    ref, cur = np.clip(ref, EPS, None), np.clip(cur, EPS, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


@dataclass
class Report:
    month: int
    model_version: str
    psi: dict[str, float]
    served: Evaluation
    reference_auc: float
    alerts: list[str] = field(default_factory=list)


def monitor(paths: Paths, month: int) -> Report:
    """Compare `month`'s features with what the serving model trained on, and judge what it served."""
    snapshot = month_start(month).isoformat()
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        current = con.execute(
            "SELECT f.*, p.churn_probability, p.model_version FROM features f "
            "JOIN predictions p USING (customer_id, snapshot_date) WHERE f.snapshot_date = $s::DATE",
            {"s": snapshot},
        ).df()
        if current.empty:
            raise SystemExit(f"no predictions for month {month}: run `mle score --month {month}` first")
        served_version = str(current["model_version"].iloc[0])
        reference = features.load(con, [month_start(m).isoformat() for m in trained_months(served_version)])

    client = mlflow.MlflowClient()
    reference_auc = float(client.get_model_version(MODEL_NAME, served_version).tags["eval_roc_auc"])
    drift = {c: psi(reference[c], current[c]) for c in CATEGORICAL + NUMERIC}
    served = evaluate_frame(current, current["churn_probability"], month, served_version)
    record(paths, served, "served")

    report = Report(month, served_version, drift, served, reference_auc)
    report.alerts += [f"drift in {c} (PSI {v:.2f})" for c, v in drift.items() if v > PSI_ALERT]
    if served.metrics["roc_auc"] < reference_auc - AUC_DROP_ALERT:
        report.alerts.append(f"ROC AUC fell to {served.metrics['roc_auc']:.3f} from {reference_auc:.3f}")
    report.alerts += [f"served model failed gate: {f}" for f in served.failures]

    paths.reports.mkdir(parents=True, exist_ok=True)
    out = paths.reports / f"monitor-{snapshot}.json"
    out.write_text(json.dumps(asdict(report), indent=2) + "\n")

    mlflow.set_experiment(MONITORING_EXPERIMENT)
    with mlflow.start_run(run_name=f"monitor-{snapshot}"):
        mlflow.set_tags({"month": snapshot, "model_version": served_version, "alert": str(bool(report.alerts))})
        mlflow.log_metrics({f"psi_{c}": v for c, v in drift.items()} | served.metrics)
        mlflow.log_artifact(str(out))
    return report
