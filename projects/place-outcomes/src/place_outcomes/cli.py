"""`places`: schools, homes, and outcomes by place, and a monthly home value forecast loop."""

import argparse
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path

# MLflow prints a hint for coding agents on import; this project doesn't use tracing.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb
import pandas as pd

from place_outcomes import analysis, data, factors, features, loop, model, report
from place_outcomes.config import Paths

REPLAY_START = date(2012, 1, 1)


def month(text: str) -> date:
    """A month as YYYY-MM (or any ISO date in it)."""
    return date.fromisoformat(text + "-01" if len(text) == 7 else text).replace(day=1)


def build(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse)) as con:
        values = data.load(con, paths.raw)
        rows = features.build(con)
        problems = features.check(con)
        last = features.latest_month(con)
        zips = con.execute("SELECT state, count(DISTINCT zip) FROM zhvi GROUP BY state ORDER BY state").fetchall()
    print(f"Zillow home values: {values:,} ZIP-months ({', '.join(f'{z} {s} ZIPs' for s, z in zips)}) through {last}")
    print(f"features with five years of history: {rows:,} ZIP-months")
    if problems:
        raise SystemExit("data quality checks failed: " + ", ".join(problems))
    if all((paths.raw / f).exists() for f in ("tract_outcomes_simple.csv", "lea_zcta.csv")):
        with duckdb.connect(str(paths.warehouse)) as con:
            factors.load(con, paths.raw)
            n = factors.build(con)
            warnings = factors.check(con)
        print(f"area factors: {n:,} ZIPs")
        for w in warnings:
            print(f"  warning: {w}")


def analysis_frame(paths: Paths) -> pd.DataFrame:
    with duckdb.connect(str(paths.warehouse), read_only=True) as con:
        df = analysis.frame(con)
    if df.empty:
        raise SystemExit("no ZIPs with every factor: run `places fetch --seda` after accepting SEDA's agreement")
    return df


def show_scores(s: analysis.Scores) -> None:
    print(f"{s.target}: {s.zips:,} ZIPs in {s.counties} counties, cross-validated R² by county")
    print(f"  baseline (area income, state) {s.baseline_r2:.3f}; linear {s.linear_r2:.3f}; boosted {s.boosted_r2:.3f}")
    for state, (base, lin, boost) in s.states.items():
        print(f"  {state} alone: baseline {base:.3f}; linear {lin:.3f}; boosted {boost:.3f}")
    for f, lost in sorted(s.adds.items(), key=lambda kv: -kv[1]):
        print(f"  {analysis.LABELS.get(f, f):<55} coef {s.coefficients[f]:+.3f}  R² lost without it {lost:+.3f}")


def show_decision(d: model.Decision) -> None:
    print(f"  challenger v{d.challenger}: {'promoted' if d.promoted else 'rejected'} ({d.reason})")


def show_step(s: loop.Step) -> None:
    if s.median_forecast is None:
        print(f"{s.as_of:%Y-%m}: no ZIPs to forecast")
    else:
        print(
            f"{s.as_of:%Y-%m}: v{s.model_version} forecasts {s.zips} ZIPs, "
            f"median 12-month change {s.median_forecast:+.1%}"
        )
    if s.model_mae is not None:
        print(
            f"  last {loop.MONITOR_MONTHS} scored months: MAE {s.model_mae:.4f} vs no change "
            f"{s.nochange_mae:.4f}, momentum {s.momentum_mae:.4f}"
        )
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
    parser = argparse.ArgumentParser(prog="places", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where data and the warehouse go")
    sub = parser.add_subparsers(dest="command", required=True)
    fe = sub.add_parser("fetch", help="download home values and area factors, then build")
    fe.add_argument(
        "--seda",
        action="store_true",
        help="also download SEDA school data; only after accepting its agreement at edopportunity.org/trends/data",
    )
    sub.add_parser("build", help="rebuild home values and features from the downloaded file")
    bo = sub.add_parser("bootstrap", help="train and promote the first champion")
    bo.add_argument("--as-of", type=month, help="YYYY-MM; default the latest month")
    st = sub.add_parser("step", help="one month of the loop: forecast, monitor, retrain if needed")
    st.add_argument("--as-of", type=month, help="YYYY-MM; default the latest month")
    rp = sub.add_parser("replay", help="bootstrap at --start, then run the loop every month since")
    rp.add_argument("--start", type=month, default=REPLAY_START)
    rp.add_argument("--end", type=month)
    rp.add_argument("--verbose", action="store_true", help="print every month, not only retrains")
    sub.add_parser("summary", help="forecast error by origin year: model, no change, and momentum")
    sub.add_parser("outcomes", help="question 1: factors against adult outcomes")
    sub.add_parser("price", help="question 2: factors against home values, and the school premium")
    rpt = sub.add_parser("report", help="write the HTML report of questions 1 and 2 under the data folder")
    rpt.add_argument("--places", type=Path, default=Path("places.local.toml"), help="ZIPs to highlight (uncommitted)")
    args = parser.parse_args(argv)
    paths = Paths(args.data_dir)

    match args.command:
        case "fetch":
            data.fetch(paths)
            data.fetch_factors(paths, seda=args.seda)
            build(paths)
        case "build":
            build(paths)
        case "bootstrap":
            show_decision(loop.bootstrap(paths, args.as_of or loop.latest(paths)))
        case "step":
            show_step(loop.step(paths, args.as_of or loop.latest(paths)))
        case "replay":
            attempts, steps = loop.replay(paths, args.start, args.end)
            for d in attempts:
                print(f"bootstrap {model.trained_as_of(d.challenger):%Y-%m}:")
                show_decision(d)
            for s in steps:
                if args.verbose or s.decision:
                    show_step(s)
            summary(paths)
        case "summary":
            summary(paths)
        case "outcomes":
            show_scores(analysis.outcomes(analysis_frame(paths)))
        case "price":
            q2 = analysis.price(analysis_frame(paths))
            show_scores(q2.scores)
            for state, value in q2.school_premium.items():
                raw = q2.school_premium_raw[state]
                print(f"  {state}: one SD better schools, {value:+.1%} home value with controls ({raw:+.1%} without)")
        case "report":
            df = analysis_frame(paths)
            out = report.write(
                paths.data_dir / "report.html",
                analysis.outcomes(df),
                analysis.price(df),
                report.highlights(args.places),
                loop.latest(paths),
            )
            print(f"wrote {out}")
