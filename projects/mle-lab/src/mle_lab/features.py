"""Volatility features and the label, in DuckDB SQL.

Realized volatility is the annualized standard deviation of daily log returns. The features at day
t use returns up to t's close; the label is the realized volatility of the next five days, so it is
only known five trading days later.
"""

import duckdb
import pandas as pd

from mle_lab.config import FEATURES, HORIZON, TARGET, TRADING_DAYS

FEATURES_SQL = f"""
CREATE OR REPLACE TABLE features AS
WITH returns AS (
    SELECT date, vix, ln(sp500 / lag(sp500) OVER (ORDER BY date)) AS ret FROM prices
),
windows AS (
    SELECT
        row_number() OVER w AS day,
        date,
        sqrt({TRADING_DAYS}) * abs(ret) AS rv_1d,
        sqrt({TRADING_DAYS} * avg(ret * ret) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)) AS rv_5d,
        sqrt({TRADING_DAYS} * avg(ret * ret) OVER (w ROWS BETWEEN 20 PRECEDING AND CURRENT ROW)) AS rv_21d,
        count(ret) OVER (w ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS past_days,
        vix / 100 AS vix,
        sqrt({TRADING_DAYS} * avg(ret * ret) OVER (w ROWS BETWEEN 1 FOLLOWING AND {HORIZON} FOLLOWING)) AS future_rv,
        count(ret) OVER (w ROWS BETWEEN 1 FOLLOWING AND {HORIZON} FOLLOWING) AS future_days
    FROM returns
    WINDOW w AS (ORDER BY date)
)
SELECT
    day, date, {", ".join(FEATURES)},
    -- The label exists only once all {HORIZON} following days have happened.
    CASE WHEN future_days = {HORIZON} THEN future_rv END AS {TARGET}
FROM windows
WHERE past_days = 21
ORDER BY date
"""


def build(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(FEATURES_SQL)
    row = con.execute("SELECT count(*) FROM features").fetchone()
    assert row is not None
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Data quality problems in `features`; empty when it is fit to use."""
    checks = {
        "fewer than a year of rows": f"SELECT count(*) < {TRADING_DAYS} FROM features",
        "null features": "SELECT count(*) > 0 FROM features WHERE " + " OR ".join(f"{c} IS NULL" for c in FEATURES),
        "volatility outside 0-500%": "SELECT count(*) > 0 FROM features WHERE least("
        + ", ".join(FEATURES)
        + ") < 0 OR greatest("
        + ", ".join(FEATURES)
        + ") > 5",
        "gap over 7 days between rows": "SELECT max(gap) > 7 FROM "
        "(SELECT date - lag(date) OVER (ORDER BY date) AS gap FROM features)",
    }
    problems = []
    for name, sql in checks.items():
        row = con.execute(sql).fetchone()
        if row is None or row[0]:
            problems.append(name)
    return problems


def day_of(con: duckdb.DuckDBPyConnection, date: str) -> int:
    """The trading-day number of the last row on or before `date`."""
    row = con.execute("SELECT max(day) FROM features WHERE date <= $d::DATE", {"d": date}).fetchone()
    if row is None or row[0] is None:
        raise SystemExit(f"no features on or before {date}")
    return int(row[0])


def labeled(con: duckdb.DuckDBPyConnection, as_of_day: int, first_day: int = 0) -> pd.DataFrame:
    """Rows whose label was known by the close of `as_of_day`: at least HORIZON days earlier.

    This is what keeps training and evaluation honest when replaying history: on any day, only
    labels that had already arrived can be used.
    """
    return con.execute(
        "SELECT * FROM features WHERE day BETWEEN $first AND $last ORDER BY day",
        {"first": first_day, "last": as_of_day - HORIZON},
    ).df()


def on_day(con: duckdb.DuckDBPyConnection, day: int) -> pd.DataFrame:
    return con.execute("SELECT * FROM features WHERE day = $d", {"d": day}).df()
