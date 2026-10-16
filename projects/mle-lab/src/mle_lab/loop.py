"""The feedback loop: each month, serve the champion, learn from the labels that come back, and
retrain behind the eval gate when monitoring says the world has moved.

One turn for month M:

1. Score M with the champion (at the start of the month, before anyone churns).
2. When M's labels land, monitor it: drift against the champion's training data, and evals of
   what was served. Both are recorded in DuckDB and MLflow.
3. If monitoring raised an alert (or retraining is forced), train challengers on the latest
   `window` labeled months before M, and evaluate them on M, the newest labeled month.
4. Promote a challenger only if it passes the gates and beats the champion on M; month M+1 is
   then served by whichever model holds the champion alias.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from mle_lab import registry, serve, train
from mle_lab.config import Paths
from mle_lab.monitor import Report, monitor

WINDOW = 4


@dataclass
class Turn:
    month: int
    report: Report
    retrained: bool
    decisions: list[registry.Decision] = field(default_factory=list)


def bootstrap(
    paths: Paths, train_months: Sequence[int], eval_month: int, kinds: Sequence[train.ModelKind]
) -> list[registry.Decision]:
    """Train the first models and promote the best one that passes the gates."""
    decisions = []
    for kind in kinds:
        train.train(paths, kind, train_months, eval_month)
        decisions.append(registry.promote(paths, eval_month))
    return decisions


def turn(
    paths: Paths,
    month: int,
    kinds: Sequence[train.ModelKind] = ("logreg", "hgb"),
    window: int = WINDOW,
    force: bool = False,
    min_gain: float = 0.0,
) -> Turn:
    serve.score(paths, month)
    report = monitor(paths, month)
    result = Turn(month, report, retrained=force or bool(report.alerts))
    if result.retrained:
        months = list(range(max(1, month - window), month))
        for kind in kinds:
            train.train(paths, kind, months, month)
            result.decisions.append(registry.promote(paths, month, min_gain))
    return result
