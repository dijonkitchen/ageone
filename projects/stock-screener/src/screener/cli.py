"""Command line: refresh data, run saved screens, look at a company."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from . import DISCLAIMER, config, pipeline, store
from .company import company_report, find_company
from .screen import Screen, all_columns, describe


def _connect(args: argparse.Namespace, read_only: bool = True):
    cfg = config.load(args.config)
    return store.connect(args.db or cfg.database, read_only=read_only), cfg


def _write(frame: pd.DataFrame, fmt: str, out: str | None, extra: dict | None = None) -> None:
    columns = [c for c in frame.columns if c != "cik"]
    if fmt == "json":
        payload = {
            "disclaimer": DISCLAIMER,
            **(extra or {}),
            "definitions": {c: describe(c) for c in columns if "." in c or c.startswith("score")},
            "rows": json.loads(frame.to_json(orient="records")),
        }
        text = json.dumps(payload, indent=2) + "\n"
    elif fmt == "csv":
        header = [f"# {DISCLAIMER}"] + [f"# {c}: {describe(c)}" for c in columns if "." in c or c.startswith("score")]
        text = "\n".join(header) + "\n" + frame.to_csv(index=False)
    else:
        with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200,
                               "display.float_format", "{:,.4g}".format):
            text = frame.drop(columns=["cik"], errors="ignore").to_string(index=False) + f"\n\n{DISCLAIMER}\n"
    if out:
        Path(out).write_text(text)
        print(f"wrote {len(frame)} rows to {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def cmd_refresh(args: argparse.Namespace) -> None:
    cfg = config.load(args.config)
    from .sec import SecClient

    client = SecClient(cfg.require_user_agent(), cfg.requests_per_second)
    con = store.connect(args.db or cfg.database)
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    pit = True if args.pit else (False if args.latest else None)
    counts = pipeline.refresh(client, con, tickers=tickers, full=args.full, pit_mode=pit, limit=args.limit,
                              log=lambda m: print(m, file=sys.stderr))
    print(", ".join(f"{v} {k}" for k, v in counts.items()) + f", {client.requests_made} requests", file=sys.stderr)


def cmd_rebuild(args: argparse.Namespace) -> None:
    con, _ = _connect(args, read_only=False)
    pipeline.rebuild(con, log=lambda m: print(m, file=sys.stderr))


def cmd_screen(args: argparse.Namespace) -> None:
    screen = Screen.load(args.file)
    if args.limit is not None:
        screen.limit = args.limit
    con, _ = _connect(args)
    _write(screen.run(con), args.format, args.out, {"screen": screen.to_dict()})


def cmd_company(args: argparse.Namespace) -> None:
    con, _ = _connect(args)
    cik = find_company(con, args.ticker)
    report = company_report(con, cik)
    if args.format == "json":
        payload = {"disclaimer": DISCLAIMER, "company": report.info,
                   "series": json.loads(report.series.reset_index().to_json(orient="records")),
                   "filings": json.loads(report.filings.to_json(orient="records")),
                   "splits": json.loads(report.splits.to_json(orient="records")),
                   "gaps": json.loads(report.gaps.to_json(orient="records"))}
        print(json.dumps(payload, indent=2, default=str))
        return
    info = report.info
    print(f"{info['name']} ({info['ticker']}), CIK {info['cik']}, {info['company_type']}, {info['currency']}")
    print(f"latest filing {info['latest_form']} {info['latest_accession']} filed {info['latest_filed']}\n")
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200,
                           "display.float_format", "{:,.4g}".format):
        print(report.series.T.to_string(), "\n")
        print("Filings:\n" + report.filings.to_string(index=False), "\n")
        if len(report.splits):
            print("Splits:\n" + report.splits.to_string(index=False), "\n")
        gaps = report.gaps[report.gaps["missing"] != ""]
        if len(gaps):
            print("Missing data:\n" + gaps.to_string(index=False), "\n")
    print(DISCLAIMER)


def cmd_columns(args: argparse.Namespace) -> None:
    for column in all_columns():
        print(f"{column}: {describe(column)}")


def cmd_app(args: argparse.Namespace) -> None:
    app = Path(__file__).with_name("app.py")
    env_args = ["--", "--db", str(args.db)] if args.db else []
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app),
                                      "--server.address", "localhost", *args.streamlit_args, *env_args]))


def cmd_record_fixture(args: argparse.Namespace) -> None:
    """Save a company's Company Facts response (gzipped) for offline tests and the spot check."""
    cfg = config.load(args.config)
    from .sec import SecClient

    client = SecClient(cfg.require_user_agent(), cfg.requests_per_second)
    rows = [r for r in client.tickers() if (r.get("ticker") or "").upper() == args.ticker.upper()]
    if not rows:
        raise SystemExit(f"{args.ticker} is not in the SEC ticker list")
    facts = pipeline._facts(client, int(rows[0]["cik"]), args.ticker.upper())
    out = Path(args.out) / f"{args.ticker.upper()}.companyfacts.json.gz"
    out.write_bytes(gzip.compress(json.dumps(facts, separators=(",", ":")).encode(), mtime=0))
    print(f"wrote {out}", file=sys.stderr)


def cmd_spot_check(args: argparse.Namespace) -> None:
    from .spot_check import run

    con, _ = _connect(args)
    raise SystemExit(0 if run(con, args.file) else 1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="screener", description=__doc__, epilog=DISCLAIMER)
    parser.add_argument("--config", type=Path, help="config file (default: config.toml, then ~/.config/ageone/stock-screener.toml)")
    parser.add_argument("--db", help="database file (default from config)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("refresh", help="load what changed at the SEC since the last run (everything, the first time)")
    p.add_argument("--tickers", help="comma-separated tickers to load instead of every listed company")
    p.add_argument("--limit", type=int, help="only the first N companies (for a trial run)")
    p.add_argument("--full", action="store_true", help="reload every company even if nothing new was filed")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--pit", action="store_true", help="point-in-time: keep values as first reported (reloads all)")
    mode.add_argument("--latest", action="store_true", help="latest filed values win (the default; reloads all if switching)")
    p.set_defaults(func=cmd_refresh)

    p = sub.add_parser("rebuild", help="recompute metrics from stored statements after editing metrics.toml (no network)")
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("screen", help="run a saved screen file")
    p.add_argument("file", type=Path)
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.add_argument("--limit", type=int, help="override the screen's row limit")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("company", help="a company's yearly series, filings, splits, and gaps")
    p.add_argument("ticker", help="ticker or CIK")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.set_defaults(func=cmd_company)

    p = sub.add_parser("columns", help="list screenable columns with their definitions")
    p.set_defaults(func=cmd_columns)

    p = sub.add_parser("app", help="open the interactive screener on localhost (other options go to streamlit run)")
    p.set_defaults(func=cmd_app)

    p = sub.add_parser("record-fixture", help="save a company's Company Facts for offline tests")
    p.add_argument("ticker")
    p.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "tests" / "fixtures"))
    p.set_defaults(func=cmd_record_fixture)

    p = sub.add_parser("spot-check", help="compare loaded values with numbers typed from 10-K filings")
    p.add_argument("file", type=Path, nargs="?", default=Path(__file__).resolve().parents[2] / "spot_check.toml")
    p.set_defaults(func=cmd_spot_check)

    args, extra = parser.parse_known_args(argv)
    if extra and args.command != "app":
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.streamlit_args = extra
    args.func(args)


if __name__ == "__main__":
    main()
