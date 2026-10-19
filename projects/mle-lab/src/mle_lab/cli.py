"""`mle`: forecast S&P 500 volatility and run its feedback loop."""

import argparse
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path

# MLflow prints a hint for coding agents on import; this lab doesn't use tracing.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from mle_lab import data, features, loop, model, serve
from mle_lab.config import Paths

REPLAY_START = "2019-01-02"


def build(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse)) as con:
        days = data.load(con, paths.raw)
        rows = features.build(con)
        problems = features.check(con)
        last = con.execute("SELECT max(date) FROM features").fetchone()
    print(f"prices: {days} days; features: {rows} rows through {last[0] if last else '?'}")
    if problems:
        raise SystemExit("data quality checks failed: " + ", ".join(problems))


def show_decision(d: model.Decision) -> None:
    print(f"  challenger v{d.challenger}: {'promoted' if d.promoted else 'rejected'} ({d.reason})")


def show_step(s: loop.Step) -> None:
    print(f"{s.date}: v{s.model_version} forecasts {s.forecast:.1%} volatility for the next week")
    if s.model_qlike is not None:
        print(f"  last {loop.MONITOR_DAYS} labeled days: QLIKE {s.model_qlike:.3f} vs baseline {s.baseline_qlike:.3f}")
    if s.alert:
        print(f"  alert: {s.alert}")
    if s.decision:
        show_decision(s.decision)


def summary(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        print(con.sql(loop.SUMMARY_SQL))
        print(
            con.sql(
                "SELECT count(*) FILTER (retrained) AS retrains, count(*) FILTER (promoted) AS promotions FROM monitoring"
            )
        )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mle", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where data and the warehouse go")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download the S&P 500 and VIX from FRED, then build features")
    sub.add_parser("build", help="rebuild prices and features from the downloaded CSVs")
    bo = sub.add_parser("bootstrap", help="train and promote the first champion")
    bo.add_argument("--as-of", default=date.today().isoformat())
    st = sub.add_parser("step", help="one day of the loop: forecast, monitor, retrain if needed")
    st.add_argument("--as-of", default=date.today().isoformat())
    rp = sub.add_parser("replay", help="bootstrap at --start, then run the loop every trading day since")
    rp.add_argument("--start", default=REPLAY_START)
    rp.add_argument("--end")
    rp.add_argument("--verbose", action="store_true", help="print every day, not only retrains")
    sub.add_parser("summary", help="forecast quality by year, model vs baseline")
    sv = sub.add_parser("serve", help="HTTP server for the champion (mlflow models serve)")
    sv.add_argument("--port", type=int, default=5001)
    args = parser.parse_args(argv)
    paths = Paths(args.data_dir)

    match args.command:
        case "fetch":
            data.fetch(paths)
            build(paths)
        case "build":
            build(paths)
        case "bootstrap":
            show_decision(loop.bootstrap(paths, args.as_of))
        case "step":
            with duckdb.connect(str(paths.warehouse), read_only=True) as con:
                day = features.day_of(con, args.as_of)
            show_step(loop.step(paths, day))
        case "replay":
            for s in loop.replay(paths, args.start, args.end):
                if args.verbose or s.decision:
                    show_step(s)
            summary(paths)
        case "summary":
            summary(paths)
        case "serve":
            serve.http(args.port)
