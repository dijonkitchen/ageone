"""Interactive screener on localhost: `screener app` (or `streamlit run app.py -- --db FILE [--prices-dir DIR]`)."""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from screener import DISCLAIMER, config, prices, store
from screener import portfolio as pf
from screener.company import company_report
from screener.metrics import WINDOWS, definitions
from screener.screen import (
    OPS,
    Filter,
    Screen,
    Weight,
    describe,
    metric_columns,
    rankable_columns,
)
from screener.valuation import LIVE, historical_ratios, live_ratios, ratio_ranges


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    parser.add_argument("--prices-db")
    parser.add_argument("--prices-dir")
    args, _ = parser.parse_known_args(sys.argv[1:])
    return args


def _db_path() -> Path:
    args = _args()
    return Path(args.db) if args.db else config.load().database


@st.cache_resource
def _connection(path: str, mtime: float):
    return store.connect(path, read_only=True)


def _price_cache(db: str) -> prices.PriceCache:
    args = _args()
    return _open_price_cache(db, args.prices_db, args.prices_dir)


@st.cache_resource
def _open_price_cache(db: str, prices_db: str | None, prices_dir: str | None) -> prices.PriceCache:
    """Quotes and history: from recorded files with --prices-dir, else the configured provider. Keys stay here."""
    args, cfg = argparse.Namespace(prices_db=prices_db, prices_dir=prices_dir), config.load()
    provider = prices.RecordedProvider(args.prices_dir) if args.prices_dir else prices.from_config(cfg.prices)
    return prices.PriceCache(args.prices_db or Path(db).with_suffix(".prices.duckdb"), provider)


@st.cache_data
def _universe(path: str, mtime: float, window: str) -> pd.DataFrame:
    """Every company's columns for a window, for slider ranges and choices."""
    con = _connection(path, mtime)
    return Screen(window=window, columns=metric_columns(), sort_by="ticker", descending=False).run(con)


def _label(column: str) -> str:
    metric, _, stat = column.partition(".")
    if metric == "live" and stat in LIVE:
        return f"{LIVE[stat].label} · live"
    spec = definitions().metrics.get(metric)
    return f"{spec.label} · {stat.replace('_', ' ')}" if spec else column


def _screen_page(con, path: str, mtime: float) -> None:
    screen: Screen = st.session_state.setdefault("screen", Screen(name="New screen"))
    universe = _universe(path, mtime, screen.window)

    with st.sidebar:
        st.subheader("Screen")
        uploaded = st.file_uploader("Load a screen file", type=["toml"])
        if uploaded is not None and st.session_state.get("loaded_name") != uploaded.name + str(uploaded.size):
            try:
                st.session_state["screen"] = screen = Screen.loads(uploaded.getvalue().decode())
                st.session_state["loaded_name"] = uploaded.name + str(uploaded.size)
                st.rerun()
            except (ValueError, KeyError) as error:
                st.error(f"Can't load that screen: {error}")
        screen.name = st.text_input("Name", screen.name)
        windows = list(WINDOWS)
        screen.window = st.selectbox("Growth window (years)", windows, index=windows.index(screen.window))
        screen.min_years = int(st.number_input("Minimum years of data", 0, 30, screen.min_years))
        exchanges = sorted(universe["exchange"].dropna().unique())
        screen.exchanges = st.multiselect("Exchanges", exchanges, [e for e in screen.exchanges if e in exchanges])
        currencies = sorted(universe["currency"].dropna().unique())
        screen.currencies = st.multiselect("Reporting currency", currencies, [c for c in screen.currencies if c in currencies])
        sic = st.text_input("SIC industry prefixes (comma-separated)", ", ".join(screen.sic_prefixes))
        screen.sic_prefixes = [s.strip() for s in sic.split(",") if s.strip()]
        recent = st.checkbox("Drop companies that stopped filing", screen.max_fiscal_year_age is not None)
        screen.max_fiscal_year_age = (
            int(st.number_input("Latest fiscal year at most this many years behind", 0, 10, screen.max_fiscal_year_age or 1))
            if recent else None
        )

    columns = rankable_columns()
    cache = _price_cache(path)
    quotes = cache.quotes()
    st.subheader("Filters")
    keep: list[Filter] = []
    for i, f in enumerate(screen.filters):
        left, mid, right, remove = st.columns([4, 1, 5, 1])
        column = left.selectbox("Column", columns, columns.index(f.column), key=f"fcol{i}", format_func=_label,
                                label_visibility="collapsed")
        op = mid.selectbox("Op", OPS, OPS.index(f.op), key=f"fop{i}", label_visibility="collapsed")
        values = (live_ratios(con, quotes)[column].dropna() if column.startswith("live.") and len(quotes)
                  else universe[column].dropna() if column in universe else pd.Series(dtype=float))
        low, high = (float(values.quantile(0.01)), float(values.quantile(0.99))) if len(values) else (0.0, 1.0)
        low, high = min(low, f.value), max(high, f.value)
        if high <= low:
            high = low + 1.0
        value = right.slider("Threshold", low, high, float(f.value), key=f"fval{i}", label_visibility="collapsed")
        if not remove.button("✕", key=f"frm{i}"):
            keep.append(Filter(column, op, value))
    screen.filters = keep
    if st.button("Add filter"):
        screen.filters.append(Filter("bvps.cagr", ">=", 0.10))
        st.rerun()

    st.subheader("Composite score")
    chosen = st.multiselect("Rank by", columns, [w.column for w in screen.score], format_func=_label)
    existing = {w.column: w for w in screen.score}
    weights = []
    for column in chosen:
        w = existing.get(column, Weight(column))
        a, b = st.columns([3, 2])
        weight = a.slider(f"Weight: {_label(column)}", 0.0, 5.0, float(w.weight), 0.5, key=f"w{column}")
        higher = b.radio("Better when", ["higher", "lower"], 0 if screen.direction(w) else 1, horizontal=True,
                         key=f"d{column}") == "higher"
        weights.append(Weight(column, weight, higher))
    screen.score = weights

    with st.expander("Columns and sort"):
        screen.columns = st.multiselect("Extra columns", columns, [c for c in screen.columns if c in columns],
                                        format_func=_label)
        sortable = ["score", "ticker", "name", "years_of_data", *columns]
        screen.sort_by = st.selectbox("Sort by", sortable, sortable.index(screen.sort_by) if screen.sort_by in sortable else 0,
                                      format_func=_label)
        screen.descending = st.checkbox("Descending", screen.descending)

    results = screen.run(con, quotes)
    if any(c.startswith("live.") for c in screen.output_columns()):
        stamp = quotes["timestamp"].max() if len(quotes) else None
        left, right = st.columns([3, 1])
        left.caption(f"Live columns use {len(quotes)} cached quotes, latest {stamp or 'none yet'}.")
        if right.button("Refresh quotes for these results"):
            cache.refresh_quotes(results["ticker"].dropna().tolist())
            st.rerun()
    st.caption(f"{len(results)} companies · {DISCLAIMER}")
    shown = results.drop(columns=["cik"])
    config_ = {c: st.column_config.NumberColumn(_label(c), help=describe(c), format="%.4g")
               for c in shown.columns if "." in c or c.startswith("score")}
    event = st.dataframe(shown, column_config=config_, hide_index=True, on_select="rerun",
                         selection_mode="multi-row", key="results")
    rows = event.selection.rows if event and event.selection else []
    selected = results.iloc[rows]
    st.session_state["selected"] = selected[["cik", "ticker", "name"]].to_dict("records")

    a, b, c, d = st.columns(4)
    a.download_button("Save screen file", screen.dumps(), file_name=f"{screen.name.lower().replace(' ', '-')}.toml")
    b.download_button(f"Download {len(selected)} selected", selected.to_csv(index=False), file_name="selected.csv",
                      disabled=selected.empty)
    if c.button("Open company", disabled=selected.empty):
        st.session_state["company"] = int(selected.iloc[0]["cik"])
        st.session_state["page"] = "Company"
        st.rerun()
    if d.button(f"Add {len(selected)} to portfolio", disabled=selected.empty):
        book: pf.Portfolio = st.session_state.setdefault("portfolio", pf.Portfolio())
        for ticker in selected["ticker"].dropna():
            book.add(ticker)
        st.session_state["page"] = "Portfolio"
        st.rerun()


def _price_ratios(con, cache: prices.PriceCache, cik: int, ticker: str) -> None:
    st.subheader("Price ratios")
    quotes = cache.refresh_quotes([ticker])
    live = live_ratios(con, quotes)
    current = live.iloc[0].to_dict() if len(live) else {}
    if not current:
        st.info(f"No quote for {ticker} from the price provider.")
    elif current.get("price_flag"):
        st.warning(f"Live ratios not computed: {current['price_flag']}.")
    else:
        q = quotes.iloc[0]
        st.caption(f"{_quote_label(q)} · fundamentals from fiscal year {int(current['live.fiscal_year'])}")
        shown = {LIVE[k[5:]].label: current[k] for k in current if k.startswith("live.") and k != "live.fiscal_year"}
        st.dataframe(pd.DataFrame([shown]), hide_index=True)
    end = prices.today()
    history = cache.history([ticker], end - timedelta(days=365 * 16), end)
    historical = historical_ratios(con, cik, history)
    if historical[["pe", "pb", "pfcf", "dividend_yield"]].notna().any().any():
        st.markdown("**At each 10-K filing date**", help="Priced at the close on the day each 10-K was filed, when its numbers became public.")
        st.dataframe(ratio_ranges(historical, current), hide_index=True)
        st.dataframe(historical, hide_index=True)


def _quote_label(q) -> str:
    kind = "last close" if q["last_close"] else ("real time" if q["realtime"] else "delayed")
    return f"{q['price']:,.2f} {q['currency'] or ''} · {kind} · {pd.Timestamp(q['timestamp']):%Y-%m-%d %H:%M} UTC · {q['source']}"


def _company_page(con) -> None:
    companies = con.execute(
        "select cik, ticker, name from companies where status = 'loaded' order by ticker"
    ).fetchdf()
    if companies.empty:
        st.info("No companies loaded yet. Run `screener refresh`.")
        return
    ciks = companies["cik"].tolist()
    labels = {r.cik: f"{r.ticker} · {r.name}" for r in companies.itertuples()}
    current = st.session_state.get("company", ciks[0])
    cik = st.selectbox("Company", ciks, ciks.index(current) if current in ciks else 0, format_func=labels.get)
    st.session_state["company"] = cik
    report = company_report(con, cik)
    info = report.info
    st.header(f"{info['name']} ({info['ticker']})")
    st.caption(f"CIK {cik} · {info['exchange']} · SIC {info['sic']} {info['sic_description'] or ''} · "
               f"{info['company_type']} · reported in {info['currency']} · {DISCLAIMER}")
    if info["currency"] and info["currency"] != "USD":
        st.warning(f"Values are in {info['currency']} as reported; no currency conversion.")
    gaps = report.gaps.set_index("metric")
    for group, title in (("per_share", "Per share (split-adjusted)"), ("profitability", "Profitability"),
                         ("balance_sheet", "Balance sheet")):
        st.subheader(title)
        metrics = [m for m in definitions().metrics.values() if m.group == group]
        for row in range(0, len(metrics), 2):
            for slot, metric in zip(st.columns(2), metrics[row:row + 2]):
                with slot:
                    st.markdown(f"**{metric.label}**", help=f"{metric.description}\n\nFormula: `{metric.formula}`")
                    if metric.name in report.series and report.series[metric.name].notna().any():
                        series = report.series[metric.name].dropna()
                        series.index = series.index.astype(str)
                        st.line_chart(series, height=180)
                    missing = gaps.loc[metric.name, "missing"] if metric.name in gaps.index else ""
                    if missing:
                        st.caption(f"Missing: {missing}")
    try:
        _price_ratios(con, _price_cache(st.session_state["db"]), cik, info["ticker"].upper())
    except Exception as error:  # noqa: BLE001 (a provider outage never breaks the page)
        st.warning(f"Price provider unavailable: {error}")
    st.subheader("Filings")
    st.dataframe(report.filings, hide_index=True, column_config={"url": st.column_config.LinkColumn("Filing index")})
    if len(report.splits):
        st.subheader("Stock splits")
        st.dataframe(report.splits, hide_index=True)


def _portfolio_page(con, path: str) -> None:
    book: pf.Portfolio = st.session_state.setdefault("portfolio", pf.Portfolio())
    st.header(book.name)
    st.warning(pf.PORTFOLIO_DISCLAIMER)
    s = book.settings
    prices_cfg = config.load().prices
    with st.sidebar:
        st.subheader("Portfolio")
        uploaded = st.file_uploader("Load a portfolio file", type=["toml"])
        if uploaded is not None and st.session_state.get("loaded_portfolio") != uploaded.name + str(uploaded.size):
            try:
                st.session_state["portfolio"] = pf.Portfolio.loads(uploaded.getvalue().decode())
                st.session_state["loaded_portfolio"] = uploaded.name + str(uploaded.size)
                st.rerun()
            except (ValueError, KeyError) as error:
                st.error(f"Can't load that portfolio: {error}")
        book.name = st.text_input("Name", book.name)
        book.value = float(st.number_input("Portfolio value", 0.0, None, float(book.value), 1000.0))
        s.fraction = float(st.slider("Kelly fraction", 0.05, 1.0, float(s.fraction), 0.05,
                                     help="Half Kelly (0.5) gives up a little growth for much less risk from errors in your returns."))
        s.risk_free = float(st.number_input("Risk-free rate", -0.05, 0.25, float(s.risk_free), 0.005, format="%.3f"))
        s.max_total = float(st.number_input("Total invested at most (1 = 100%, above is leverage)", 0.1, 3.0, float(s.max_total), 0.1))
        capped = st.checkbox("Cap each holding's weight", s.max_weight is not None)
        s.max_weight = float(st.slider("Maximum weight", 0.01, 1.0, float(s.max_weight or 0.25), 0.01)) if capped else None
        s.lookback_years = float(st.number_input("Covariance lookback (years)", 1.0, 15.0, float(s.lookback_years), 1.0))
        s.growth_cap = float(st.number_input("Growth cap for suggested returns", 0.0, 0.5, float(s.growth_cap), 0.01))
        s.sensitivity = float(st.number_input("Sensitivity: lower every return by", 0.0, 0.2, float(s.sensitivity), 0.005, format="%.3f"))
        interval = int(st.number_input("Refresh quotes every (seconds)", prices_cfg.min_refresh_seconds, 3600,
                                       max(prices_cfg.refresh_seconds, prices_cfg.min_refresh_seconds),
                                       help="The provider's rate limit sets the minimum (config: min_refresh_seconds)."))

    left, right = st.columns([3, 1])
    ticker = left.text_input("Add a ticker", placeholder="e.g. KO", label_visibility="collapsed", key="add_ticker")
    if right.button("Add ticker", key="add_ticker_button") and ticker:
        book.add(ticker)
        st.rerun()
    if not book.holdings:
        st.info("Add tickers here, or select rows on the Screen page and add them.")
        return
    edited = st.data_editor(
        pd.DataFrame([{"ticker": h.ticker, "shares held": h.shares, "return method": h.method,
                       "expected return (typed)": h.expected_return, "remove": False} for h in book.holdings]),
        hide_index=True, disabled=["ticker"], key="holdings",
        column_config={"return method": st.column_config.SelectboxColumn(options=list(pf.METHODS), required=True,
                                                                         help="; ".join(f"{k}: {v}" for k, v in pf.METHOD_LABELS.items())),
                       "expected return (typed)": st.column_config.NumberColumn(format="%.3f", help="Used when the method is manual.")})
    book.holdings = [
        pf.Holding(r["ticker"], None if pd.isna(r["shares held"]) else float(r["shares held"]), r["return method"],
                   None if pd.isna(r["expected return (typed)"]) else float(r["expected return (typed)"]))
        for r in edited.to_dict("records") if not r["remove"]
    ]
    if len(book.holdings) < len(edited):
        st.rerun()
    st.download_button("Save portfolio file", book.dumps(), file_name=f"{book.name.lower().replace(' ', '-')}.toml")

    @st.fragment(run_every=interval)
    def live() -> None:
        cache = _price_cache(path)
        try:
            quotes = cache.refresh_quotes(book.tickers())
            start, end = pf.history_window(s)
            history = cache.history(book.tickers(), start, end)
        except Exception as error:  # noqa: BLE001
            st.error(f"Price provider unavailable: {error}")
            return
        result = pf.view(con, book, quotes, history)
        st.subheader("Holdings")
        for q in quotes.itertuples(index=False):
            st.caption(f"{q.ticker}: {_quote_label(q._asdict())}")
        shown = result.rows[["ticker", "live.price", "live.market_cap", "live.pe", "live.pb", "live.pfcf", "live.fcf_yield",
                             "live.dividend_yield", "live.ev_ebit", *[c for c in pf.KEY_METRICS if c in result.rows],
                             "fcf", "earnings", "historical", "method", "mu"]]
        st.dataframe(shown.rename(columns={"fcf": "suggested (FCF)", "earnings": "suggested (earnings)",
                                           "historical": "suggested (historical)", "mu": "return used"}),
                     hide_index=True, column_config={c: st.column_config.NumberColumn(format="%.4g") for c in shown.columns if c != "ticker"})
        for problem in result.problems:
            st.warning(problem)
        if not result.allocation:
            return
        a = result.allocation
        st.subheader(f"Allocation at {s.fraction:g} Kelly")
        st.dataframe(a.holdings.rename(columns={"mu": "return used", "held": "shares held", "trade": "shares to trade",
                                                "weight_if_lower": f"weight if returns {s.sensitivity:.1%} lower"}),
                     hide_index=True, column_config={"weight": st.column_config.NumberColumn(format="percent"),
                                                     "current_weight": st.column_config.NumberColumn(format="percent")})
        c1, c2, c3 = st.columns(3)
        c1.metric("Invested", f"{a.invested:,.0f}")
        c2.metric("Cash left", f"{a.cash:,.0f}")
        c3.metric("Covariance", f"{result.days} days", f"shrinkage {result.shrinkage:.2f}", delta_color="off")
        st.dataframe(pd.DataFrame([{"": f"{s.fraction:g} Kelly", **a.chosen}, {"": "Full Kelly", **a.full}]), hide_index=True,
                     column_config={k: st.column_config.NumberColumn(format="percent") for k in a.chosen})
        st.bar_chart(a.holdings.set_index("ticker")[["weight", "weight_if_lower"]], stack=False)

    live()


def main() -> None:
    st.set_page_config(page_title="Stock screener", layout="wide")
    path = _db_path()
    if not path.exists():
        st.error(f"No database at {path}. Run `screener refresh` first.")
        return
    mtime = path.stat().st_mtime
    con = _connection(str(path), mtime)
    st.session_state["db"] = str(path)
    pages = ["Screen", "Company", "Portfolio"]
    page = st.sidebar.radio("Page", pages, index=pages.index(st.session_state.get("page", "Screen")))
    st.session_state["page"] = page
    refreshed = store.get_meta(con, "refreshed_at")
    st.sidebar.caption(f"Data refreshed {refreshed or 'never'} · {path.name}")
    if page == "Screen":
        _screen_page(con, str(path), mtime)
    elif page == "Company":
        _company_page(con)
    else:
        _portfolio_page(con, str(path))


main()
