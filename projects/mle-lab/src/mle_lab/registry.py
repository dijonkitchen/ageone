"""Promote the challenger to champion only when it passes the eval gates and beats the champion on the same month."""

from dataclasses import dataclass

import mlflow
from mlflow.exceptions import MlflowException

from mle_lab.config import CHALLENGER, CHAMPION, MODEL_NAME, Paths
from mle_lab.evaluate import Evaluation, evaluate, record


@dataclass(frozen=True)
class Decision:
    promoted: bool
    reason: str
    challenger: Evaluation
    champion: Evaluation | None


def version_for(alias: str) -> str | None:
    try:
        return str(mlflow.MlflowClient().get_model_version_by_alias(MODEL_NAME, alias).version)
    except MlflowException:
        return None


def decide(challenger: Evaluation, champion: Evaluation | None, min_gain: float) -> tuple[bool, str]:
    if not challenger.passed:
        return False, "challenger failed gates: " + "; ".join(challenger.failures)
    if champion is None:
        return True, "no champion yet"
    if not champion.passed:
        return True, "champion failed gates: " + "; ".join(champion.failures)
    gain = challenger.metrics["roc_auc"] - champion.metrics["roc_auc"]
    if gain >= min_gain:
        return True, f"ROC AUC gain {gain:+.3f} >= {min_gain}"
    return False, f"ROC AUC gain {gain:+.3f} < {min_gain}"


def promote(paths: Paths, eval_month: int, min_gain: float = 0.0) -> Decision:
    """Evaluate challenger and champion on `eval_month`, record both, and move the champion alias if earned."""
    challenger_version = version_for(CHALLENGER)
    if challenger_version is None:
        raise SystemExit(f"no {CHALLENGER} version of {MODEL_NAME}: run `mle train` first")
    champion_version = version_for(CHAMPION)

    challenger = evaluate(paths, challenger_version, eval_month)
    record(paths, challenger, CHALLENGER)
    champion = None
    if champion_version is not None and champion_version != challenger_version:
        champion = evaluate(paths, champion_version, eval_month)
        record(paths, champion, CHAMPION)

    promoted, reason = decide(challenger, champion, min_gain)
    client = mlflow.MlflowClient()
    client.set_model_version_tag(MODEL_NAME, challenger_version, "eval_roc_auc", f"{challenger.metrics['roc_auc']:.4f}")
    client.set_model_version_tag(MODEL_NAME, challenger_version, "promotion", "promoted" if promoted else "rejected")
    client.set_model_version_tag(MODEL_NAME, challenger_version, "promotion_reason", reason)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION, challenger_version)
    return Decision(promoted, reason, challenger, champion)
