"""Synthetic raw data for a subscription service: customers, their events, and who churned each month.

Churn in a month depends on the previous month's activity, so features built from the 30 days
before a snapshot can predict it. New customers sign up every month, so the population's tenure
stays steady. From month `drift_from` on, a (pretend) app release lowers logins and raises support
tickets, and frustrated customers who file tickets churn more readily than before: the inputs
drift (monitoring sees it) and so does what they mean (only retraining on new labels fixes it).
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from mle_lab.config import DEFAULT_MONTHS, Months

PLANS = np.array(["basic", "standard", "premium"])
REGIONS = np.array(["na", "eu", "apac"])
EPOCH = date(2026, 1, 1)
MONTHLY_SIGNUPS = 0.08  # Of the starting customer count, about the monthly churn rate.


def month_start(month: int) -> date:
    """First day of generated month `month` (0-based from EPOCH)."""
    return date(EPOCH.year + (EPOCH.month - 1 + month) // 12, (EPOCH.month - 1 + month) % 12 + 1, 1)


def generate(out_dir: Path, customers: int = 2000, months: Months = DEFAULT_MONTHS, seed: int = 7) -> None:
    """Write customers.parquet, events.parquet, and labels.parquet to `out_dir`."""
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The first cohort's tenure is roughly exponential, as steady churn and signups leave it;
    # later cohorts sign up during months 0 to total-2.
    signups = int(customers * MONTHLY_SIGNUPS)
    n = customers + signups * (months.total - 1)
    ids = np.arange(1, n + 1)
    joined = np.concatenate([np.full(customers, -1), np.repeat(np.arange(months.total - 1), signups)])
    signup = [
        EPOCH - timedelta(days=1 + int(min(rng.exponential(365), 5 * 365)))
        if j < 0
        else month_start(int(j)) + timedelta(days=int(rng.integers(0, 28)))
        for j in joined
    ]
    plan = rng.choice(PLANS, n, p=[0.5, 0.35, 0.15])
    region = rng.choice(REGIONS, n, p=[0.45, 0.35, 0.2])
    engagement = rng.gamma(shape=2.0, scale=4.0, size=n)  # Mean logins a month.
    plan_lift = np.select([plan == "premium", plan == "standard"], [-0.6, -0.3], 0.0)

    churned_before = np.zeros(n, dtype=bool)
    event_frames: list[pd.DataFrame] = []
    label_frames: list[pd.DataFrame] = []
    previous: dict[str, np.ndarray] | None = None

    for m in range(months.total):
        start = month_start(m)
        days = (month_start(m + 1) - start).days
        drifted = m >= months.drift_from

        if previous is not None:
            # A snapshot covers customers who joined before last month began, so each has a full month of history.
            at_risk = (joined < m - 1) & ~churned_before
            # Few logins, support tickets, and failed payments last month raise the chance of churning this month.
            ticket_weight = 1.5 if m > months.drift_from else 0.7
            logit = (
                -1.8
                - 0.3 * previous["login"]
                + ticket_weight * previous["support_ticket"]
                + 1.2 * previous["payment_failed"]
                + plan_lift
            )
            churned = at_risk & (rng.random(n) < 1 / (1 + np.exp(-logit)))
            label_frames.append(
                pd.DataFrame(
                    {"customer_id": ids[at_risk], "snapshot_date": pd.Timestamp(start), "churned": churned[at_risk]}
                )
            )
            churned_before |= churned

        active = (joined < m) & ~churned_before
        counts = {
            "login": rng.poisson(engagement * (0.55 if drifted else 1.0)),
            "support_ticket": rng.poisson(0.9 if drifted else 0.3, n),
            "payment_failed": rng.poisson(0.08, n),
        }
        for kind, k in counts.items():
            k = np.where(active, k, 0)
            owners = np.repeat(ids, k)
            offsets = rng.integers(0, days * 24 * 3600, owners.size)
            event_frames.append(
                pd.DataFrame(
                    {
                        "customer_id": owners,
                        "event_time": pd.Timestamp(start) + pd.to_timedelta(offsets, unit="s"),
                        "kind": kind,
                    }
                )
            )
        previous = {kind: np.where(active, k, 0) for kind, k in counts.items()}

    pd.DataFrame(
        {"customer_id": ids, "signup_date": pd.to_datetime(signup), "plan": plan, "region": region}
    ).to_parquet(out_dir / "customers.parquet", index=False)
    pd.concat(event_frames, ignore_index=True).sort_values("event_time").to_parquet(
        out_dir / "events.parquet", index=False
    )
    pd.concat(label_frames, ignore_index=True).to_parquet(out_dir / "labels.parquet", index=False)
