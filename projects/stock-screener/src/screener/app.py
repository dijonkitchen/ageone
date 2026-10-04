"""Interactive screener on localhost: `screener app` (or `streamlit run app.py -- --db FILE`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from screener import DISCLAIMER, config, store
from screener.company import company_report
from screener.metrics import WINDOWS, definitions
from screener.screen import OPS, Filter, Screen, Weight, describe, metric_columns


def _db_path() -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    args, _ = parser.parse_known_args(sys.argv[1:])
    return Path(args.db) if args.db else config.load().database


@st.cache_resource
def _connection(path: str, mtime: float):
    return store.connect(path, read_only=True)


@st.cache_data
def _universe(path: str, mtime: float, window: str) -> pd.DataFrame:
    """Every company's columns for a window, for slider ranges and choices."""
    con = _connection(path, mtime)
    return Screen(window=window, columns=metric_columns(), sort_by="ticker", descending=False).run(con)


def _label(column: str) -> str:
    metric, _, stat = column.partition(".")
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

    columns = metric_columns()
    st.subheader("Filters")
    keep: list[Filter] = []
    for i, f in enumerate(screen.filters):
        left, mid, right, remove = st.columns([4, 1, 5, 1])
        column = left.selectbox("Column", columns, columns.index(f.column), key=f"fcol{i}", format_func=_label,
                                label_visibility="collapsed")
        op = mid.selectbox("Op", OPS, OPS.index(f.op), key=f"fop{i}", label_visibility="collapsed")
        values = universe[column].dropna() if column in universe else pd.Series(dtype=float)
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

    results = screen.run(con)
    st.caption(f"{len(results)} companies · {DISCLAIMER}")
    shown = results.drop(columns=["cik"])
    config_ = {c: st.column_config.NumberColumn(_label(c), help=describe(c), format="%.4g")
               for c in shown.columns if "." in c or c.startswith("score")}
    event = st.dataframe(shown, column_config=config_, hide_index=True, on_select="rerun",
                         selection_mode="multi-row", key="results")
    rows = event.selection.rows if event and event.selection else []
    selected = results.iloc[rows]
    st.session_state["selected"] = selected[["cik", "ticker", "name"]].to_dict("records")

    a, b, c = st.columns(3)
    a.download_button("Save screen file", screen.dumps(), file_name=f"{screen.name.lower().replace(' ', '-')}.toml")
    b.download_button(f"Download {len(selected)} selected", selected.to_csv(index=False), file_name="selected.csv",
                      disabled=selected.empty)
    if c.button("Open company", disabled=selected.empty):
        st.session_state["company"] = int(selected.iloc[0]["cik"])
        st.session_state["page"] = "Company"
        st.rerun()


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
    st.subheader("Filings")
    st.dataframe(report.filings, hide_index=True, column_config={"url": st.column_config.LinkColumn("Filing index")})
    if len(report.splits):
        st.subheader("Stock splits")
        st.dataframe(report.splits, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Stock screener", layout="wide")
    path = _db_path()
    if not path.exists():
        st.error(f"No database at {path}. Run `screener refresh` first.")
        return
    mtime = path.stat().st_mtime
    con = _connection(str(path), mtime)
    pages = ["Screen", "Company"]
    page = st.sidebar.radio("Page", pages, index=pages.index(st.session_state.get("page", "Screen")))
    st.session_state["page"] = page
    refreshed = store.get_meta(con, "refreshed_at")
    st.sidebar.caption(f"Data refreshed {refreshed or 'never'} · {path.name}")
    if page == "Screen":
        _screen_page(con, str(path), mtime)
    else:
        _company_page(con)


main()
