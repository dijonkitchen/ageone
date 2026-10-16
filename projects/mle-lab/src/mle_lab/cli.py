"""`mle`: run each stage of the system, one turn of the feedback loop, or everything in order."""

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

# MLflow prints a hint for coding agents on import; this lab doesn't use tracing.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import duckdb

from mle_lab import data, features, loop, monitor, registry, serve, train
from mle_lab.config import Months, Paths

KINDS: tuple[train.ModelKind, ...] = ("logreg", "hgb")


def run_features(paths: Paths) -> None:
    with duckdb.connect(str(paths.warehouse)) as con:
        rows = features.build(con, paths.raw)
        problems = features.check(con)
    print(f"features: {rows} rows")
    if problems:
        raise SystemExit("data quality checks failed: " + ", ".join(problems))


def show_decision(d: registry.Decision) -> None:
    verdict = "promoted" if d.promoted else "rejected"
    print(
        f"  challenger v{d.challenger.model_version} ROC AUC {d.challenger.metrics['roc_auc']:.3f}: {verdict} ({d.reason})"
    )


def show_report(r: monitor.Report) -> None:
    m = r.served.metrics
    print(
        f"month {r.month}: served v{r.model_version}, ROC AUC {m['roc_auc']:.3f}, calibration gap {m['calibration_gap']:.3f}"
    )
    for alert in r.alerts:
        print(f"  alert: {alert}")


def show_turn(t: loop.Turn) -> None:
    show_report(t.report)
    for d in t.decisions:
        show_decision(d)


def main(argv: Sequence[str] | None = None) -> None:
    months = Months()
    parser = argparse.ArgumentParser(prog="mle", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where data, warehouse, and reports go")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write synthetic raw Parquet data")
    gen.add_argument("--customers", type=int, default=2000)
    gen.add_argument("--seed", type=int, default=7)
    sub.add_parser("features", help="build and check the DuckDB features table")
    tr = sub.add_parser("train", help="train, track, and register a challenger on the first months")
    tr.add_argument("--model", choices=KINDS, default="logreg")
    pr = sub.add_parser("promote", help="evaluate the challenger and make it champion if it earns it")
    pr.add_argument("--month", type=int, default=months.validation, help="labeled month to evaluate on")
    pr.add_argument("--min-gain", type=float, default=0.0)
    sc = sub.add_parser("score", help="batch score a month with the champion")
    sc.add_argument("--month", type=int, required=True)
    mo = sub.add_parser("monitor", help="drift and served-model evals for a scored month; exits 1 on alerts")
    mo.add_argument("--month", type=int, required=True)
    tu = sub.add_parser("turn", help="one turn of the feedback loop: score, monitor, retrain on alert, promote")
    tu.add_argument("--month", type=int, required=True)
    tu.add_argument("--window", type=int, default=loop.WINDOW, help="labeled months to retrain on")
    tu.add_argument("--force", action="store_true", help="retrain even without an alert")
    sv = sub.add_parser("serve", help="HTTP server for the champion (mlflow models serve)")
    sv.add_argument("--port", type=int, default=5001)
    al = sub.add_parser("all", help="generate, build features, bootstrap a champion, then a loop turn per month")
    al.add_argument("--customers", type=int, default=2000)
    args = parser.parse_args(argv)
    paths = Paths(args.data_dir)

    match args.command:
        case "generate":
            data.generate(paths.raw, args.customers, seed=args.seed)
        case "features":
            run_features(paths)
        case "train":
            t = train.train(paths, args.model, months.train, months.validation)
            print(f"trained {args.model}: version {t.version}, eval ROC AUC {t.metrics['eval_roc_auc']:.3f}")
        case "promote":
            show_decision(registry.promote(paths, args.month, args.min_gain))
        case "score":
            print(f"scored {serve.score(paths, args.month)} customers")
        case "monitor":
            report = monitor.monitor(paths, args.month)
            show_report(report)
            if report.alerts:
                raise SystemExit(1)
        case "turn":
            show_turn(loop.turn(paths, args.month, KINDS, args.window, args.force))
        case "serve":
            serve.http(args.port)
        case "all":
            data.generate(paths.raw, args.customers)
            run_features(paths)
            print(
                f"bootstrap: train on months {months.train.start}-{months.train.stop - 1}, evaluate on {months.validation}"
            )
            for d in loop.bootstrap(paths, months.train, months.validation, KINDS):
                show_decision(d)
            for month in months.production:
                show_turn(loop.turn(paths, month, KINDS))
