"""The daily feedback loop, and a replay of it over history.

Each morning (`as_of`), when demand is known through the end of yesterday:

1. Forecast every hour of tomorrow with the champion, next to the naive forecast.
2. Score the champion against naive over the last MONITOR_DAYS forecasted days whose actuals are in.
3. Retrain when the champion has fallen behind naive, or when its training is RETRAIN_DAYS old, at
   most once every COOLDOWN_DAYS. Promote the challenger only through the gate in `model.promote`.

Forecasts go to DuckDB one row per hour, and monitoring one row per day; training runs and the
registry go to MLflow. Replaying years of days makes the loop's feedback a minute instead of years.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import duckdb

from mle_lab import features, model
from mle_lab.config import CHAMPION, TARGET, Paths

MONITOR_DAYS = 14
RETRAIN_DAYS = 28
COOLDOWN_DAYS = 7

TABLES = """
CREATE TABLE IF NOT EXISTS forecasts (
    utc_end TIMESTAMP PRIMARY KEY, date DATE, made_on DATE, model_version VARCHAR, forecast DOUBLE, naive DOUBLE
);
CREATE TABLE IF NOT EXISTS monitoring (
    as_of DATE PRIMARY KEY, model_version VARCHAR, labeled_days BIGINT,
    model_mape DOUBLE, naive_mape DOUBLE, alert VARCHAR, retrained BOOLEAN, promoted BOOLEAN
);
"""

# Forecasted hours whose actuals are known on the morning of $as_of, over the last $days such days.
SCORED_SQL = f"""
SELECT avg(abs(f.forecast - x.{TARGET}) / x.{TARGET}) AS model_mape,
       avg(abs(f.naive - x.{TARGET}) / x.{TARGET}) AS naive_mape,
       count(DISTINCT f.date) AS days
FROM forecasts f JOIN features x USING (utc_end)
WHERE f.date BETWEEN $as_of - $days::INT AND $as_of - 1 AND x.{TARGET} IS NOT NULL
"""


@dataclass
class Step:
    as_of: date
    target: date
    model_version: str
    hours: int
    peak: float | None
    model_mape: float | None
    naive_mape: float | None
    alert: str | None
    decision: model.Decision | None


def _last_attempt(con: duckdb.DuckDBPyConnection) -> date | None:
    row = con.execute("SELECT max(as_of) FROM monitoring WHERE retrained").fetchone()
    return None if row is None else row[0]


def step(paths: Paths, as_of: date) -> Step:
    """Run the loop for the morning of `as_of`."""
    s, con = _step(paths, as_of, duckdb.connect(str(paths.warehouse)))
    con.close()
    return s


def _step(paths: Paths, as_of: date, con: duckdb.DuckDBPyConnection) -> tuple[Step, duckdb.DuckDBPyConnection]:
    """One morning on an open connection, returning the connection to keep using.

    Training and promotion open the warehouse themselves, so the connection is closed around a
    retrain and a new one returned.
    """
    champion = model.version_for(CHAMPION)
    if champion is None:
        raise SystemExit("no champion: run `mle bootstrap` first")
    try:
        con.execute(TABLES)
        target = as_of + timedelta(days=1)
        hours = features.day(con, target)
        peak = None
        if len(hours):
            hours["forecast"] = model.predict(champion, hours)
            hours["made_on"] = as_of
            hours["model_version"] = champion
            con.register("new_forecasts", hours)
            con.execute(
                "INSERT OR REPLACE INTO forecasts "
                "SELECT utc_end, date, made_on, model_version, forecast, naive_forecast FROM new_forecasts"
            )
            con.unregister("new_forecasts")
            peak = float(hours["forecast"].max())

        scored = con.execute(SCORED_SQL, {"as_of": as_of, "days": MONITOR_DAYS}).fetchone()
        assert scored is not None
        model_m, naive_m, days = scored
        alert = None
        if days < MONITOR_DAYS:
            model_m = naive_m = None
        elif model_m > naive_m:
            alert = f"champion behind naive over {MONITOR_DAYS} days: MAPE {model_m:.2%} > {naive_m:.2%}"
        age = model.age(champion, as_of).days
        if alert is None and age >= RETRAIN_DAYS:
            alert = f"champion trained {age} days ago"
        last = _last_attempt(con)
        cooling = last is not None and (as_of - last).days < COOLDOWN_DAYS

        decision = None
        if alert and not cooling:
            con.close()
            model.train(paths, as_of)
            decision = model.promote(paths, as_of)
            con = duckdb.connect(str(paths.warehouse))
        con.execute(
            "INSERT OR REPLACE INTO monitoring VALUES ($as_of, $v, $n, $mm, $nm, $alert, $r, $p)",
            {
                "as_of": as_of,
                "v": champion,
                "n": days,
                "mm": model_m,
                "nm": naive_m,
                "alert": alert,
                "r": decision is not None,
                "p": decision is not None and decision.promoted,
            },
        )
    except BaseException:
        con.close()
        raise
    return Step(as_of, target, champion, len(hours), peak, model_m, naive_m, alert, decision), con


def bootstrap(paths: Paths, as_of: date) -> model.Decision:
    """Train and promote the first champion as of `as_of`."""
    model.train(paths, as_of)
    return model.promote(paths, as_of)


def last_morning(paths: Paths) -> date:
    """The latest morning the data supports: the day after the last day with any demand."""
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        row = con.execute(f"SELECT max(date) FROM features WHERE {TARGET} IS NOT NULL").fetchone()
    assert row is not None and row[0] is not None, "no labeled features: run `mle build`"
    return row[0] + timedelta(days=1)  # type: ignore[no-any-return]


def replay(paths: Paths, start: date, end: date | None = None) -> tuple[list[model.Decision], list[Step]]:
    """Bootstrap a champion on the morning of `start`, then run the loop every morning through `end`.

    No model ships until one beats naive, so a rejected bootstrap is tried again COOLDOWN_DAYS later.
    """
    end = end or last_morning(paths)
    with duckdb.connect(str(paths.warehouse)) as con:
        con.execute("DROP TABLE IF EXISTS forecasts; DROP TABLE IF EXISTS monitoring")
    as_of = start
    attempts = [bootstrap(paths, as_of)]
    while not attempts[-1].promoted:
        as_of += timedelta(days=COOLDOWN_DAYS)
        if as_of > end:
            return attempts, []
        attempts.append(bootstrap(paths, as_of))
    steps = []
    con = duckdb.connect(str(paths.warehouse))
    try:
        while as_of <= end:
            s, con = _step(paths, as_of, con)
            steps.append(s)
            as_of += timedelta(days=1)
    finally:
        con.close()
    return attempts, steps


SUMMARY_SQL = f"""
SELECT
    strftime(f.date, '%Y-%m') AS month,
    count(DISTINCT f.date) AS days,
    round(avg(x.{TARGET})) AS mean_mw,
    round(100 * avg(abs(f.forecast - x.{TARGET}) / x.{TARGET}), 2) AS model_mape,
    round(100 * avg(abs(f.naive - x.{TARGET}) / x.{TARGET}), 2) AS naive_mape,
    round(100 * avg(abs(x.operator_forecast - x.{TARGET}) / x.{TARGET}), 2) AS operator_mape,
    count(DISTINCT f.model_version) AS versions
FROM forecasts f JOIN features x USING (utc_end)
WHERE x.{TARGET} IS NOT NULL
GROUP BY ROLLUP (month) ORDER BY month NULLS LAST
"""
