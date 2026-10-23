"""Features for a day-ahead demand forecast, in DuckDB SQL.

A forecast for day D is made on the morning of D-1, when demand is known through the end of D-2,
the same time the grid operator publishes its own day-ahead forecast. So every feature for D uses
data from D-2 or earlier: calendar fields, demand at the same hour two and seven days before, and
D-2's mean, minimum, and maximum. Each row also carries the two forecasts to measure against: the
seasonal naive one (same hour last week) and the operator's.
"""

from datetime import date, timedelta

import duckdb
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from mle_lab.config import FEATURES, TARGET, TIMEZONE

FEATURES_SQL = """
CREATE OR REPLACE TABLE features AS
WITH hours AS (
    -- Every hour from the first in the data through two days past the last, so tomorrow has rows to forecast.
    SELECT unnest(generate_series(
        (SELECT min(utc_end) FROM demand), (SELECT max(utc_end) FROM demand) + INTERVAL 2 DAY, INTERVAL 1 HOUR
    )) AS utc_end
),
local AS (
    -- Hour-ending timestamps: the hour ending 01:00 local starts at 00:00 on that day.
    SELECT utc_end, timezone($tz, (utc_end - INTERVAL 1 HOUR) AT TIME ZONE 'UTC') AS local_start FROM hours
),
daily AS (
    SELECT l.local_start::DATE AS date, avg(d.demand) AS mean, min(d.demand) AS min, max(d.demand) AS max
    FROM local l JOIN demand d USING (utc_end) GROUP BY ALL
)
SELECT
    l.utc_end,
    l.local_start::DATE AS date,
    hour(l.local_start) AS hour,
    isodow(l.local_start) AS dow,
    dayofyear(l.local_start) AS doy,
    (h.date IS NOT NULL)::INT AS holiday,
    d2.demand AS lag_2d,
    d7.demand AS lag_7d,
    p.mean AS prev_mean,
    p.min AS prev_min,
    p.max AS prev_max,
    d7.demand AS naive_forecast,
    d.operator_forecast,
    d.demand AS {target}
FROM local l
LEFT JOIN demand d USING (utc_end)
LEFT JOIN demand d2 ON d2.utc_end = l.utc_end - INTERVAL 2 DAY
LEFT JOIN demand d7 ON d7.utc_end = l.utc_end - INTERVAL 7 DAY
LEFT JOIN daily p ON p.date = l.local_start::DATE - 2
LEFT JOIN holidays h ON h.date = l.local_start::DATE
WHERE {complete}
ORDER BY l.utc_end
""".format(target=TARGET, complete=" AND ".join(f"{c} IS NOT NULL" for c in ["d2.demand", "d7.demand", "p.mean"]))


def build(con: duckdb.DuckDBPyConnection) -> int:
    span = con.execute(
        "SELECT min(utc_end)::DATE::TIMESTAMP, (max(utc_end)::DATE + 3)::TIMESTAMP FROM demand"
    ).fetchone()
    assert span is not None
    first, last = span
    holidays = USFederalHolidayCalendar().holidays(start=first, end=last)
    con.execute("CREATE OR REPLACE TABLE holidays AS SELECT unnest($d::DATE[]) AS date", {"d": list(holidays.date)})
    con.execute(FEATURES_SQL, {"tz": TIMEZONE})
    row = con.execute("SELECT count(*) FROM features").fetchone()
    assert row is not None
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Data quality problems; empty when the data is fit to use."""
    checks = {
        "under a year of hours": "SELECT count(*) < 365 * 24 FROM demand",
        "over 1% of hours missing demand": "SELECT avg((demand IS NULL)::INT) > 0.01 FROM demand "
        "WHERE utc_end < (SELECT max(utc_end) - INTERVAL 2 DAY FROM demand)",
        "implausible demand (under a third or over triple the median)": "SELECT count(*) > 0 FROM demand, "
        "(SELECT median(demand) AS m FROM demand) WHERE demand < m / 3 OR demand > m * 3",
        "missing hours in the data": "SELECT max(gap) > INTERVAL 1 HOUR FROM "
        "(SELECT utc_end - lag(utc_end) OVER (ORDER BY utc_end) AS gap FROM demand)",
    }
    problems = []
    for name, sql in checks.items():
        row = con.execute(sql).fetchone()
        if row is None or row[0]:
            problems.append(name)
    return problems


def labeled(con: duckdb.DuckDBPyConnection, as_of: date) -> pd.DataFrame:
    """Hours whose actual demand was known on the morning of `as_of`: days through `as_of` - 1.

    Everything that trains, evaluates, or monitors goes through this, so a replay of history only
    ever sees what was known on the day it replays.
    """
    return con.execute(
        f"SELECT * FROM features WHERE date <= $last AND {TARGET} IS NOT NULL ORDER BY utc_end",
        {"last": as_of - timedelta(days=1)},
    ).df()


def day(con: duckdb.DuckDBPyConnection, target: date) -> pd.DataFrame:
    """The hours of `target` to forecast."""
    return con.execute("SELECT * FROM features WHERE date = $d ORDER BY utc_end", {"d": target}).df()


def model_input(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[FEATURES].astype("float64")
