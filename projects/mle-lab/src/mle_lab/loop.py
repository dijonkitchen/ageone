"""The daily feedback loop, and a replay of it over history.

Each trading day, after the close:

1. Forecast the next five days' volatility with the champion, next to the baseline's forecast.
2. Labels arrive for the forecasts made five trading days ago. Score the champion against the
   baseline over the last MONITOR_DAYS forecasts whose labels are in.
3. Retrain when the champion has fallen behind the baseline, or when its training is older than
   RETRAIN_DAYS. Promote the challenger only through the gate in `model.promote`.

Forecasts and monitoring go to DuckDB, one row a day; training runs and the registry go to MLflow.
Replaying years of days makes the loop's feedback minutes instead of years.
"""

from dataclasses import dataclass

import duckdb

from mle_lab import features, model
from mle_lab.config import CHAMPION, HORIZON, TARGET, Paths

MONITOR_DAYS = 21
RETRAIN_DAYS = 63
COOLDOWN_DAYS = 21  # After a retrain attempt, wait before trying again.

TABLES = """
CREATE TABLE IF NOT EXISTS forecasts (
    day BIGINT PRIMARY KEY, date DATE, model_version VARCHAR, forecast DOUBLE, baseline DOUBLE
);
CREATE TABLE IF NOT EXISTS monitoring (
    day BIGINT PRIMARY KEY, date DATE, model_version VARCHAR, labeled BIGINT,
    model_qlike DOUBLE, baseline_qlike DOUBLE, alert VARCHAR, retrained BOOLEAN, promoted BOOLEAN
);
"""


@dataclass
class Step:
    date: str
    model_version: str
    forecast: float
    model_qlike: float | None
    baseline_qlike: float | None
    alert: str | None
    decision: model.Decision | None


def _last_attempt(con: duckdb.DuckDBPyConnection) -> int | None:
    row = con.execute("SELECT max(day) FROM monitoring WHERE retrained").fetchone()
    return None if row is None or row[0] is None else int(row[0])


def step(paths: Paths, day: int) -> Step:
    """Run one day of the loop for trading day number `day`."""
    s, con = _step(paths, day, duckdb.connect(str(paths.warehouse)))
    con.close()
    return s


def _step(paths: Paths, day: int, con: duckdb.DuckDBPyConnection) -> tuple[Step, duckdb.DuckDBPyConnection]:
    """One day on an open connection, returning the connection to keep using.

    Training and promotion open the warehouse themselves, so the connection is closed around a
    retrain and a new one returned.
    """
    champion = model.version_for(CHAMPION)
    if champion is None:
        raise SystemExit("no champion: run `mle bootstrap` first")
    try:
        con.execute(TABLES)
        today = features.on_day(con, day)
        date = str(today["date"].iloc[0].date())
        forecast = float(model.predict(champion, today)[0])
        con.execute(
            "INSERT OR REPLACE INTO forecasts VALUES ($day, $date::DATE, $v, $f, $b)",
            {"day": day, "date": date, "v": champion, "f": forecast, "b": float(today["rv_5d"].iloc[0])},
        )
        # Forecasts whose labels have arrived by today's close.
        matured = con.execute(
            f"SELECT f.forecast, f.baseline, x.{TARGET} AS realized FROM forecasts f JOIN features x USING (day) "
            "WHERE f.day <= $day - $h ORDER BY f.day DESC LIMIT $n",
            {"day": day, "h": HORIZON, "n": MONITOR_DAYS},
        ).df()
        last_attempt = _last_attempt(con)
        trained_day = features.day_of(con, model.trained_as_of(champion))

        model_q = base_q = None
        alert = None
        if len(matured) == MONITOR_DAYS:
            realized = matured["realized"].to_numpy()
            model_q = model.qlike(realized, matured["forecast"].to_numpy())
            base_q = model.qlike(realized, matured["baseline"].to_numpy())
            if model_q > base_q:
                alert = f"champion behind baseline over {MONITOR_DAYS} days: QLIKE {model_q:.3f} > {base_q:.3f}"
        if alert is None and day - trained_day >= RETRAIN_DAYS:
            alert = f"champion trained {day - trained_day} days ago"
        cooling = last_attempt is not None and day - last_attempt < COOLDOWN_DAYS

        decision = None
        if alert and not cooling:
            con.close()
            model.train(paths, date)
            decision = model.promote(paths, date)
            con = duckdb.connect(str(paths.warehouse))
        con.execute(
            "INSERT OR REPLACE INTO monitoring VALUES ($day, $date::DATE, $v, $n, $mq, $bq, $alert, $r, $p)",
            {
                "day": day,
                "date": date,
                "v": champion,
                "n": len(matured),
                "mq": model_q,
                "bq": base_q,
                "alert": alert,
                "r": decision is not None,
                "p": decision is not None and decision.promoted,
            },
        )
    except BaseException:
        con.close()
        raise
    return Step(date, champion, forecast, model_q, base_q, alert, decision), con


def bootstrap(paths: Paths, as_of: str) -> model.Decision:
    """Train and promote the first champion as of `as_of`."""
    model.train(paths, as_of)
    return model.promote(paths, as_of)


def replay(paths: Paths, start: str, end: str | None = None) -> list[Step]:
    """Bootstrap a champion as of `start`, then run the loop for every trading day after it."""
    with duckdb.connect(str(paths.warehouse)) as con:
        con.execute("DROP TABLE IF EXISTS forecasts; DROP TABLE IF EXISTS monitoring")
        first = features.day_of(con, start)
        last = features.day_of(con, end) if end else features.day_of(con, "9999-12-31")
    bootstrap(paths, start)
    steps = []
    con = duckdb.connect(str(paths.warehouse))
    try:
        for day in range(first + 1, last + 1):
            s, con = _step(paths, day, con)
            steps.append(s)
    finally:
        con.close()
    return steps


SUMMARY_SQL = f"""
SELECT
    year(f.date) AS year,
    count(*) AS days,
    round(avg(x.{TARGET}), 3) AS mean_realized,
    round(sqrt(avg((f.forecast - x.{TARGET})^2)), 4) AS model_rmse,
    round(sqrt(avg((f.baseline - x.{TARGET})^2)), 4) AS baseline_rmse,
    round(avg(power(x.{TARGET} / f.forecast, 2) - ln(power(x.{TARGET} / f.forecast, 2)) - 1), 3) AS model_qlike,
    round(avg(power(x.{TARGET} / f.baseline, 2) - ln(power(x.{TARGET} / f.baseline, 2)) - 1), 3) AS baseline_qlike,
    count(DISTINCT f.model_version) AS versions
FROM forecasts f JOIN features x USING (day)
WHERE x.{TARGET} IS NOT NULL
GROUP BY ALL ORDER BY year
"""
