"""Command line: refresh data, run saved screens, look at a company, price it, and allocate a portfolio."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

from . import DISCLAIMER, config, pipeline, prices, store
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


def price_cache(args: argparse.Namespace, cfg: config.Config | None = None) -> prices.PriceCache:
    """The price cache, fed by recorded files with --prices-dir (offline) or by the configured provider."""
    cfg = cfg or config.load(args.config)
    provider = prices.RecordedProvider(args.prices_dir) if args.prices_dir else prices.from_config(cfg.prices)
    path = args.prices_db or (Path(args.db).with_suffix(".prices.duckdb") if args.db else cfg.prices_database)
    return prices.PriceCache(path, provider)


def _tickers(values: list[str]) -> list[str]:
    return [t.strip().upper() for v in values for t in v.split(",") if t.strip()]


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
    con, cfg = _connect(args)
    quotes = None
    if args.quotes:
        cache = price_cache(args, cfg)
        quotes = cache.quotes()
        cache.close()
    _write(screen.run(con, quotes), args.format, args.out, {"screen": screen.to_dict()})


def cmd_quotes(args: argparse.Namespace) -> None:
    cache = price_cache(args)
    quotes = cache.refresh_quotes(_tickers(args.tickers))
    cache.close()
    quotes["delay"] = ["last close" if c else ("real time" if r else "delayed") for c, r in zip(quotes["last_close"], quotes["realtime"])]
    _write(quotes.drop(columns=["realtime", "last_close"]), args.format, None)


def cmd_prices(args: argparse.Namespace) -> None:
    cache = price_cache(args)
    end = prices.today()
    history = cache.history(_tickers(args.tickers), end - timedelta(days=round(365.25 * args.years)), end)
    cache.close()
    for ticker, group in history.groupby("ticker"):
        print(f"{ticker}: {len(group)} daily closes, {group['date'].min():%Y-%m-%d} to {group['date'].max():%Y-%m-%d}")


def cmd_ratios(args: argparse.Namespace) -> None:
    from .valuation import historical_ratios, live_ratios, ratio_ranges

    con, cfg = _connect(args)
    cik = find_company(con, args.ticker)
    ticker = con.execute("select upper(ticker) from companies where cik = ?", [cik]).fetchone()[0]
    cache = price_cache(args, cfg)
    quotes = cache.refresh_quotes([ticker])
    end = prices.today()
    history = cache.history([ticker], end - timedelta(days=round(365.25 * args.years)), end)
    cache.close()
    live = live_ratios(con, quotes)
    current = live.iloc[0].to_dict() if len(live) else {}
    historical = historical_ratios(con, cik, history)
    ranges = ratio_ranges(historical, current)
    if args.format == "json":
        print(json.dumps({"disclaimer": DISCLAIMER, "live": current, "historical": json.loads(historical.to_json(orient="records")),
                          "ranges": json.loads(ranges.to_json(orient="records"))}, indent=2, default=str))
        return
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200,
                           "display.float_format", "{:,.4g}".format):
        if current.get("price_flag"):
            print(f"Live ratios not computed: {current['price_flag']}")
        print(pd.Series({k: v for k, v in current.items() if k.startswith("live.")}).to_string(), "\n")
        print(historical.to_string(index=False), "\n")
        print(ranges.to_string(index=False), "\n")
    print(DISCLAIMER)


def cmd_portfolio(args: argparse.Namespace) -> None:
    from . import portfolio as pf

    book = pf.Portfolio.load(args.file)
    if args.value is not None:
        book.value = args.value
    con, cfg = _connect(args)
    cache = price_cache(args, cfg)
    quotes = cache.refresh_quotes(book.tickers())
    start, end = pf.history_window(book.settings)
    history = cache.history(book.tickers(), start, end)
    cache.close()
    result = pf.view(con, book, quotes, history)
    for problem in result.problems:
        print(problem, file=sys.stderr)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200,
                           "display.float_format", "{:,.4g}".format):
        print(result.rows[["ticker", "live.price", "live.pe", "live.pb", "live.fcf_yield", "method", "mu"]].to_string(index=False), "\n")
        if result.allocation:
            a = result.allocation
            print(a.holdings[["ticker", "mu", "price", "weight", "dollars", "shares", "held", "trade", "weight_if_lower"]].to_string(index=False))
            print(f"\ncash left {a.cash:,.2f} of {book.value:,.2f}; covariance from {result.days} days, shrinkage {result.shrinkage:.2f}")
            for label, stats in ((f"{book.settings.fraction:g} Kelly", a.chosen), ("full Kelly", a.full)):
                print(f"{label}: expected return {stats['expected_return']:.2%}, volatility {stats['volatility']:.2%}, "
                      f"growth {stats['growth']:.2%}")
    print(f"\n{pf.PORTFOLIO_DISCLAIMER}")
    if not result.allocation:
        raise SystemExit(1)


def cmd_record_prices(args: argparse.Namespace) -> None:
    """Save quotes and daily history from the configured provider as files RecordedProvider (--prices-dir) reads."""
    cfg = config.load(args.config)
    provider = prices.from_config(cfg.prices)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tickers = _tickers(args.tickers)
    end = prices.today()
    history = provider.history(tickers, end - timedelta(days=round(365.25 * args.years)), end)
    for ticker, group in history.groupby("ticker"):
        group.assign(date=group["date"].dt.strftime("%Y-%m-%d"))[["date", "close"]].to_csv(out / f"{ticker}.prices.csv", index=False)
    quotes = provider.quote(tickers)
    path = out / "quotes.csv"
    if path.exists():
        old = pd.read_csv(path)
        quotes = pd.concat([old[~old["ticker"].isin(quotes["ticker"])], quotes], ignore_index=True).sort_values("ticker")
    quotes.to_csv(path, index=False)
    print(f"wrote {len(history)} closes and {len(quotes)} quotes to {out}", file=sys.stderr)


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
    parser.add_argument("--prices-db", help="price cache file (default: next to the database, ending .prices.duckdb)")
    parser.add_argument("--prices-dir", help="read quotes and history from recorded files here instead of the provider")
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
    p.add_argument("--quotes", action="store_true", help="fill live.* columns from the last cached quotes (see 'quotes')")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("quotes", help="fetch and cache live quotes, with their time, source, and delay")
    p.add_argument("tickers", nargs="+")
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.set_defaults(func=cmd_quotes)

    p = sub.add_parser("prices", help="fetch and cache daily price history")
    p.add_argument("tickers", nargs="+")
    p.add_argument("--years", type=float, default=15)
    p.set_defaults(func=cmd_prices)

    p = sub.add_parser("ratios", help="a company's live price ratios and historical ratios at each 10-K filing date")
    p.add_argument("ticker", help="ticker or CIK")
    p.add_argument("--years", type=float, default=15, help="years of price history to use")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.set_defaults(func=cmd_ratios)

    p = sub.add_parser("portfolio", help="allocate a portfolio file by fractional Kelly")
    p.add_argument("file", type=Path)
    p.add_argument("--value", type=float, help="portfolio value (default: the file's)")
    p.set_defaults(func=cmd_portfolio)

    p = sub.add_parser("record-prices", help="save quotes and daily history for offline tests (--prices-dir)")
    p.add_argument("tickers", nargs="+")
    p.add_argument("--years", type=float, default=15)
    p.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "prices"))
    p.set_defaults(func=cmd_record_prices)

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
