"""`mle`: forecast tomorrow's hourly grid demand and run its feedback loop."""

import argparse
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path

# MLflow prints a hint for coding agents on import; this lab doesn't use tracing.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from mle_lab import data, features, loop, model, serve
from mle_lab.config import REGION, Paths

REPLAY_START = date(2024, 1, 1)


def build(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse)) as con:
        hours = data.load(con, paths.raw)
        rows = features.build(con)
        problems = features.check(con)
        last = con.execute("SELECT max(date) FROM features").fetchone()
    print(f"{REGION} demand: {hours} hours; features: {rows} hours through {last[0] if last else '?'}")
    if problems:
        raise SystemExit("data quality checks failed: " + ", ".join(problems))


def show_decision(d: model.Decision) -> None:
    print(f"  challenger v{d.challenger}: {'promoted' if d.promoted else 'rejected'} ({d.reason})")


def show_step(s: loop.Step) -> None:
    if s.peak is None:
        print(f"{s.as_of}: no features for {s.target} yet")
    else:
        print(f"{s.as_of}: v{s.model_version} forecasts {s.hours} hours of {s.target}, peaking at {s.peak:,.0f} MW")
    if s.model_mape is not None:
        print(f"  last {loop.MONITOR_DAYS} days: MAPE {s.model_mape:.2%} vs naive {s.naive_mape:.2%}")
    if s.alert:
        print(f"  alert: {s.alert}")
    if s.decision:
        show_decision(s.decision)


def summary(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        con.sql(loop.SUMMARY_SQL).show(max_rows=1000)
        print(
            con.sql(
                "SELECT count(*) FILTER (retrained) AS retrains, count(*) FILTER (promoted) AS promotions FROM monitoring"
            )
        )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mle", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where data and the warehouse go")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download EIA-930 balance files, then build features")
    sub.add_parser("build", help="rebuild demand and features from the downloaded files")
    bo = sub.add_parser("bootstrap", help="train and promote the first champion")
    bo.add_argument("--as-of", type=date.fromisoformat)
    st = sub.add_parser("step", help="one morning of the loop: forecast tomorrow, monitor, retrain if needed")
    st.add_argument("--as-of", type=date.fromisoformat)
    rp = sub.add_parser("replay", help="bootstrap at --start, then run the loop every morning since")
    rp.add_argument("--start", type=date.fromisoformat, default=REPLAY_START)
    rp.add_argument("--end", type=date.fromisoformat)
    rp.add_argument("--verbose", action="store_true", help="print every day, not only retrains")
    sub.add_parser("summary", help="forecast error by month: model, naive, and operator")
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
            show_decision(loop.bootstrap(paths, args.as_of or loop.last_morning(paths)))
        case "step":
            show_step(loop.step(paths, args.as_of or loop.last_morning(paths)))
        case "replay":
            attempts, steps = loop.replay(paths, args.start, args.end)
            for d in attempts:
                print(f"bootstrap {model.trained_as_of(d.challenger)}:")
                show_decision(d)
            for s in steps:
                if args.verbose or s.decision:
                    show_step(s)
            summary(paths)
        case "summary":
            summary(paths)
        case "serve":
            serve.http(args.port)
