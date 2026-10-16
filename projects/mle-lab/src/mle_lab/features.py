"""Point-in-time features in DuckDB SQL, straight from the raw Parquet files, plus data quality checks."""

from pathlib import Path

import duckdb
import pandas as pd

from mle_lab.config import FEATURES, LABEL, NUMERIC

# Each snapshot sees only events strictly before it, so no feature leaks the month it predicts.
FEATURES_SQL = """
CREATE OR REPLACE TABLE features AS
WITH snapshots AS (
    SELECT customer_id, CAST(snapshot_date AS DATE) AS snapshot_date, churned
    FROM read_parquet($labels)
),
activity AS (
    SELECT
        s.customer_id,
        s.snapshot_date,
        count(*) FILTER (WHERE e.kind = 'login' AND e.event_time >= s.snapshot_date - INTERVAL 30 DAY) AS logins_30d,
        count(*) FILTER (WHERE e.kind = 'support_ticket' AND e.event_time >= s.snapshot_date - INTERVAL 30 DAY) AS tickets_30d,
        count(*) FILTER (WHERE e.kind = 'payment_failed' AND e.event_time >= s.snapshot_date - INTERVAL 30 DAY) AS payment_failures_30d,
        max(e.event_time) FILTER (WHERE e.kind = 'login') AS last_login
    FROM snapshots s
    LEFT JOIN read_parquet($events) e
        ON e.customer_id = s.customer_id AND e.event_time < s.snapshot_date
    GROUP BY ALL
)
SELECT
    s.customer_id,
    s.snapshot_date,
    c.plan,
    c.region,
    date_diff('day', CAST(c.signup_date AS DATE), s.snapshot_date) AS tenure_days,
    a.logins_30d,
    a.tickets_30d,
    a.payment_failures_30d,
    -- Never logged in counts as since signup.
    date_diff('day', CAST(coalesce(a.last_login, c.signup_date) AS DATE), s.snapshot_date) AS days_since_login,
    s.churned
FROM snapshots s
JOIN read_parquet($customers) c USING (customer_id)
JOIN activity a USING (customer_id, snapshot_date)
ORDER BY s.snapshot_date, s.customer_id
"""


def build(con: duckdb.DuckDBPyConnection, raw: Path) -> int:
    """Rebuild the `features` table from the raw Parquet files; return its row count."""
    con.execute(
        FEATURES_SQL,
        {
            "labels": str(raw / "labels.parquet"),
            "events": str(raw / "events.parquet"),
            "customers": str(raw / "customers.parquet"),
        },
    )
    row = con.execute("SELECT count(*) FROM features").fetchone()
    assert row is not None
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Data quality problems in the `features` table; empty when it is fit to train on."""
    checks = {
        "no rows": "SELECT count(*) = 0 FROM features",
        "duplicate customer snapshots": (
            "SELECT count(*) > 0 FROM (SELECT 1 FROM features GROUP BY customer_id, snapshot_date HAVING count(*) > 1)"
        ),
        "null features or labels": "SELECT count(*) > 0 FROM features WHERE "
        + " OR ".join(f"{c} IS NULL" for c in [*FEATURES, LABEL]),
        "negative counts or ages": "SELECT count(*) > 0 FROM features WHERE least(tenure_days, logins_30d, "
        "tickets_30d, payment_failures_30d, days_since_login) < 0",
        "label rate outside 1-60%": "SELECT avg(churned::INT) NOT BETWEEN 0.01 AND 0.6 FROM features",
    }
    problems = []
    for name, sql in checks.items():
        row = con.execute(sql).fetchone()
        if row is None or row[0]:
            problems.append(name)
    return problems


def load(con: duckdb.DuckDBPyConnection, months: list[str]) -> pd.DataFrame:
    """Feature rows for the given snapshot dates (ISO `YYYY-MM-DD`)."""
    return con.execute(
        "SELECT * FROM features WHERE snapshot_date IN (SELECT unnest($months)::DATE) ORDER BY snapshot_date, customer_id",
        {"months": months},
    ).df()


def model_input(frame: pd.DataFrame) -> pd.DataFrame:
    """The columns a model takes, with counts as floats so the MLflow signature allows missing values."""
    return frame[FEATURES].astype({c: "float64" for c in NUMERIC})
