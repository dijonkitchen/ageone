"""Features and labels for the 12-month home value forecast, one row per ZIP and origin month.

A row for origin month A uses only values published for months up to A: log changes over the past
1 to 60 months, recent volatility, the ZIP's level against its state's median, and state and metro
momentum in the same month. Its label is the log change from A to A + HORIZON, which is known only
once that month's value is published, so a model as of month T trains only on origins A <= T - HORIZON.
"""

from datetime import date

import duckdb
import pandas as pd

from place_outcomes.config import CATEGORICAL, FEATURES, HORIZON, TARGET

BUILD_SQL = f"""
CREATE OR REPLACE TABLE features AS
WITH span AS (
    SELECT zip, any_value(state) AS state, any_value(metro) AS metro, min(month) AS first, max(month) AS last
    FROM zhvi GROUP BY zip
),
-- A dense month grid per ZIP, so a missing month is a gap, never a silently shifted lag.
grid AS (
    SELECT zip, state, metro, unnest(generate_series(first, last, INTERVAL 1 MONTH))::DATE AS month FROM span
),
v AS (
    SELECT g.*, ln(z.value) AS lv FROM grid g LEFT JOIN zhvi z USING (zip, month)
),
w AS (
    SELECT *,
        lv - lag(lv, 1) OVER p AS r1,
        lv - lag(lv, 3) OVER p AS r3,
        lv - lag(lv, 6) OVER p AS r6,
        lv - lag(lv, 12) OVER p AS r12,
        lv - lag(lv, 24) OVER p AS r24,
        lv - lag(lv, 60) OVER p AS r60,
        lead(lv, {HORIZON}) OVER p - lv AS {TARGET}
    FROM v WINDOW p AS (PARTITION BY zip ORDER BY month)
)
SELECT zip, state, metro, month,
    r1, r3, r6, r12, r24, r60,
    stddev_samp(r1) OVER (PARTITION BY zip ORDER BY month ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS vol12,
    lv - median(lv) OVER (PARTITION BY state, month) AS rel_level,
    avg(r1) OVER (PARTITION BY state, month) AS state_r1,
    avg(r12) OVER (PARTITION BY state, month) AS state_r12,
    coalesce(avg(r12) OVER (PARTITION BY metro, month), avg(r12) OVER (PARTITION BY state, month)) AS metro_r12,
    month(month) AS moy,
    {TARGET},
    month + INTERVAL {HORIZON} MONTH AS label_month
FROM w
WHERE lv IS NOT NULL
"""


def build(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(BUILD_SQL)
    row = con.execute("SELECT count(*) FROM features WHERE r60 IS NOT NULL").fetchone()
    assert row is not None
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection, min_zips_per_state: int = 10) -> list[str]:
    """Data quality problems that should stop the pipeline; empty when the data looks sound."""
    problems = []
    dupes = con.execute("SELECT count(*) - count(DISTINCT (zip, month)) FROM zhvi").fetchone()
    if dupes and dupes[0]:
        problems.append(f"{dupes[0]} duplicate ZIP-months")
    bad = con.execute("SELECT count(*) FROM zhvi WHERE value < 10000 OR value > 50000000").fetchone()
    if bad and bad[0]:
        problems.append(f"{bad[0]} implausible home values")
    for state, zips in con.execute(
        "SELECT state, count(DISTINCT zip) FROM zhvi WHERE month = (SELECT max(month) FROM zhvi) GROUP BY state"
    ).fetchall():
        if zips < min_zips_per_state:
            problems.append(f"only {zips} ZIPs in {state} in the latest month")
    gaps = con.execute(
        "SELECT count(*) FROM features WHERE r1 IS NULL AND month > (SELECT min(month) FROM features)"
    ).fetchone()
    total = con.execute("SELECT count(*) FROM features").fetchone()
    if gaps and total and total[0] and gaps[0] / total[0] > 0.02:
        problems.append(f"{gaps[0]} of {total[0]} ZIP-months follow a missing month")
    return problems


def latest_month(con: duckdb.DuckDBPyConnection) -> date:
    row = con.execute("SELECT max(month) FROM features").fetchone()
    assert row is not None and row[0] is not None, "no features: run `places build`"
    return row[0]  # type: ignore[no-any-return]


def origins(con: duckdb.DuckDBPyConnection, first: date, last: date) -> pd.DataFrame:
    """Rows for origin months in [first, last] with full feature history (labels may be unknown)."""
    frame: pd.DataFrame = con.execute(
        "SELECT * FROM features WHERE month BETWEEN $first AND $last AND r60 IS NOT NULL AND vol12 IS NOT NULL "
        "ORDER BY month, zip",
        {"first": first, "last": last},
    ).df()
    return frame


def labeled(con: duckdb.DuckDBPyConnection, first: date, last: date, as_of: date) -> pd.DataFrame:
    """Origins in [first, last] whose labels are published by month `as_of`."""
    frame = origins(con, first, last)
    known = (frame["label_month"] <= pd.Timestamp(as_of)) & frame[TARGET].notna()
    out: pd.DataFrame = frame[known].reset_index(drop=True)
    return out


def model_input(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[FEATURES].astype(float)
    for column in CATEGORICAL:
        out[column] = (frame[column] == "CA").astype(float)  # The two states, as one 0/1 column.
    return out
