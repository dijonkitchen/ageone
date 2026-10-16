from pathlib import Path

import duckdb
import pandas as pd

from mle_lab import features
from mle_lab.config import Paths


def test_generated_features_pass_quality_checks(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse)) as con:
        assert features.check(con) == []


def test_features_only_see_events_before_the_snapshot(lab: Paths, tmp_path: Path) -> None:
    """A burst of events on and after a snapshot date must not change that snapshot's features."""
    with duckdb.connect(str(lab.warehouse)) as con:
        before = con.execute("SELECT * FROM features ORDER BY customer_id, snapshot_date").df()
        customer, snapshot = con.execute("SELECT customer_id, snapshot_date FROM features LIMIT 1").fetchone() or (0, 0)

        events = pd.read_parquet(lab.raw / "events.parquet")
        late = pd.DataFrame(
            {
                "customer_id": customer,
                "event_time": [pd.Timestamp(snapshot) + pd.Timedelta(hours=h) for h in range(0, 48, 2)],
                "kind": "support_ticket",
            }
        )
        pd.concat([events, late]).to_parquet(lab.raw / "events.parquet", index=False)
        features.build(con, lab.raw)
        after = con.execute("SELECT * FROM features ORDER BY customer_id, snapshot_date").df()

    row = (before.customer_id == customer) & (before.snapshot_date == snapshot)
    pd.testing.assert_frame_equal(before[row], after[row])


def test_counts_cover_the_30_days_before(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(
        {"customer_id": [1], "signup_date": [pd.Timestamp("2025-06-01")], "plan": ["basic"], "region": ["eu"]}
    ).to_parquet(raw / "customers.parquet")
    pd.DataFrame(
        {
            "customer_id": [1, 1, 1, 1],
            "event_time": pd.to_datetime(
                ["2026-01-15", "2026-02-20", "2026-02-28T23:59", "2026-03-01"], format="ISO8601"
            ),
            "kind": ["login", "login", "support_ticket", "login"],
        }
    ).to_parquet(raw / "events.parquet")
    pd.DataFrame({"customer_id": [1], "snapshot_date": [pd.Timestamp("2026-03-01")], "churned": [False]}).to_parquet(
        raw / "labels.parquet"
    )
    with duckdb.connect() as con:
        features.build(con, raw)
        row = con.execute("SELECT * FROM features").df().iloc[0]
    # 2026-01-15 is more than 30 days back, and 2026-03-01 is the snapshot itself.
    assert (row.logins_30d, row.tickets_30d, row.days_since_login) == (1, 1, 9)
    assert row.tenure_days == 273


def test_quality_checks_catch_duplicates_and_nulls() -> None:
    with duckdb.connect() as con:
        con.execute(
            "CREATE TABLE features AS SELECT * FROM (VALUES "
            "(1, DATE '2026-03-01', 'basic', 'eu', 10, 1, 0, 0, 2, true), "
            "(1, DATE '2026-03-01', 'basic', NULL, 10, 1, 0, 0, 2, false)) "
            "t(customer_id, snapshot_date, plan, region, tenure_days, logins_30d, tickets_30d, "
            "payment_failures_30d, days_since_login, churned)"
        )
        problems = features.check(con)
    assert "duplicate customer snapshots" in problems
    assert "null features or labels" in problems
