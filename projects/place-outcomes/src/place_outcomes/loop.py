"""The monthly feedback loop, and a replay of it over history.

Each month (`as_of`), once that month's home values are published:

1. Forecast every ZIP's log change over the next HORIZON months with the champion, next to both baselines.
2. Score the forecasts whose labels have just come in (origins MONITOR_MONTHS deep, ending at
   as_of - HORIZON) against the baselines.
3. Retrain when the champion has fallen behind the better baseline, or its training is RETRAIN_MONTHS
   old, at most once every COOLDOWN_MONTHS. Promote the challenger only through `model.promote`'s gate.

Forecasts go to DuckDB one row per ZIP and origin month, and monitoring one row per month; training
runs and the registry go to MLflow. A replay over 15 years of months takes a few minutes.
"""

from dataclasses import dataclass
from datetime import date

import duckdb

from place_outcomes import features, model, months
from place_outcomes.config import CHAMPION, HORIZON, TARGET, Paths

MONITOR_MONTHS = 6
RETRAIN_MONTHS = 12
COOLDOWN_MONTHS = 3

TABLES = """
CREATE TABLE IF NOT EXISTS forecasts (
    zip VARCHAR, month DATE, model_version VARCHAR, forecast DOUBLE, nochange DOUBLE, momentum DOUBLE,
    PRIMARY KEY (zip, month)
);
CREATE TABLE IF NOT EXISTS monitoring (
    as_of DATE PRIMARY KEY, model_version VARCHAR, zips BIGINT, scored_months BIGINT,
    model_mae DOUBLE, nochange_mae DOUBLE, momentum_mae DOUBLE, alert VARCHAR, retrained BOOLEAN, promoted BOOLEAN
);
"""

# Forecasts whose labels are published by $as_of, over the newest $months such origin months.
SCORED_SQL = f"""
SELECT avg(abs(f.forecast - x.{TARGET})) AS model_mae,
       avg(abs(f.nochange - x.{TARGET})) AS nochange_mae,
       avg(abs(f.momentum - x.{TARGET})) AS momentum_mae,
       count(DISTINCT f.month) AS scored_months
FROM forecasts f JOIN features x USING (zip, month)
WHERE f.month BETWEEN $first AND $last AND x.label_month <= $as_of AND x.{TARGET} IS NOT NULL
"""


@dataclass
class Step:
    as_of: date
    model_version: str
    zips: int
    median_forecast: float | None
    model_mae: float | None
    nochange_mae: float | None
    momentum_mae: float | None
    alert: str | None
    decision: model.Decision | None


def _last_attempt(con: duckdb.DuckDBPyConnection) -> date | None:
    row = con.execute("SELECT max(as_of) FROM monitoring WHERE retrained").fetchone()
    return None if row is None else row[0]


def step(paths: Paths, as_of: date) -> Step:
    """Run the loop for month `as_of`."""
    s, con = _step(paths, as_of, duckdb.connect(str(paths.warehouse)))
    con.close()
    return s


def _step(paths: Paths, as_of: date, con: duckdb.DuckDBPyConnection) -> tuple[Step, duckdb.DuckDBPyConnection]:
    """One month on an open connection, returning the connection to keep using.

    Training and promotion open the warehouse themselves, so the connection is closed around a
    retrain and a new one returned.
    """
    champion = model.version_for(CHAMPION)
    if champion is None:
        raise SystemExit("no champion: run `places bootstrap` first")
    try:
        con.execute(TABLES)
        rows = features.origins(con, as_of, as_of)
        median = None
        if len(rows):
            rows["forecast"] = model.predict(champion, rows)
            rows["model_version"] = champion
            for name, values in model.baselines(rows).items():
                rows[name] = values
            con.register("new_forecasts", rows)
            con.execute(
                "INSERT OR REPLACE INTO forecasts "
                "SELECT zip, month, model_version, forecast, nochange, momentum FROM new_forecasts"
            )
            con.unregister("new_forecasts")
            median = float(rows["forecast"].median())

        last = months.add(as_of, -HORIZON)
        scored = con.execute(
            SCORED_SQL, {"first": months.add(last, -(MONITOR_MONTHS - 1)), "last": last, "as_of": as_of}
        ).fetchone()
        assert scored is not None
        model_m, nochange_m, momentum_m, scored_months = scored
        alert = None
        if scored_months < MONITOR_MONTHS:
            model_m = nochange_m = momentum_m = None
        elif model_m > min(nochange_m, momentum_m):
            alert = (
                f"champion behind a baseline over {MONITOR_MONTHS} months: MAE {model_m:.4f} > "
                f"{min(nochange_m, momentum_m):.4f}"
            )
        age = months.between(model.trained_as_of(champion), as_of)
        if alert is None and age >= RETRAIN_MONTHS:
            alert = f"champion trained {age} months ago"
        attempted = _last_attempt(con)
        cooling = attempted is not None and months.between(attempted, as_of) < COOLDOWN_MONTHS

        decision = None
        if alert and not cooling:
            con.close()
            model.train(paths, as_of)
            decision = model.promote(paths, as_of)
            con = duckdb.connect(str(paths.warehouse))
        con.execute(
            "INSERT OR REPLACE INTO monitoring VALUES ($as_of, $v, $z, $n, $mm, $nm, $mo, $alert, $r, $p)",
            {
                "as_of": as_of,
                "v": champion,
                "z": len(rows),
                "n": scored_months,
                "mm": model_m,
                "nm": nochange_m,
                "mo": momentum_m,
                "alert": alert,
                "r": decision is not None,
                "p": decision is not None and decision.promoted,
            },
        )
    except BaseException:
        con.close()
        raise
    return Step(as_of, champion, len(rows), median, model_m, nochange_m, momentum_m, alert, decision), con


def bootstrap(paths: Paths, as_of: date) -> model.Decision:
    """Train and promote the first champion as of month `as_of`."""
    model.train(paths, as_of)
    return model.promote(paths, as_of)


def latest(paths: Paths) -> date:
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        return features.latest_month(con)


def replay(paths: Paths, start: date, end: date | None = None) -> tuple[list[model.Decision], list[Step]]:
    """Bootstrap a champion as of month `start`, then run the loop every month through `end`.

    No model ships until one beats both baselines, so a rejected bootstrap is tried again
    COOLDOWN_MONTHS later.
    """
    end = end or latest(paths)
    with duckdb.connect(str(paths.warehouse)) as con:
        con.execute("DROP TABLE IF EXISTS forecasts; DROP TABLE IF EXISTS monitoring")
    as_of = months.first_of(start)
    attempts = [bootstrap(paths, as_of)]
    while not attempts[-1].promoted:
        as_of = months.add(as_of, COOLDOWN_MONTHS)
        if as_of > end:
            return attempts, []
        attempts.append(bootstrap(paths, as_of))
    steps = []
    con = duckdb.connect(str(paths.warehouse))
    try:
        while as_of <= end:
            s, con = _step(paths, as_of, con)
            steps.append(s)
            as_of = months.add(as_of, 1)
    finally:
        con.close()
    return attempts, steps


SUMMARY_SQL = f"""
SELECT
    CAST(year(f.month) AS VARCHAR) AS origin_year,
    count(*) AS forecasts,
    round(100 * avg(abs(f.forecast - x.{TARGET})), 2) AS model_mae_pct,
    round(100 * avg(abs(f.nochange - x.{TARGET})), 2) AS nochange_mae_pct,
    round(100 * avg(abs(f.momentum - x.{TARGET})), 2) AS momentum_mae_pct,
    count(DISTINCT f.model_version) AS versions
FROM forecasts f JOIN features x USING (zip, month)
WHERE x.{TARGET} IS NOT NULL
GROUP BY ROLLUP (origin_year) ORDER BY origin_year NULLS LAST
"""
