"""Price ratios: live ones from a quote and the latest annual fundamentals, and historical ones at each 10-K filing date.

Per-share values are split-adjusted to the latest filing's basis and prices to today's, so both use the same shares
as long as no split happened after the latest 10-K. A company whose filings and price are in different currencies,
or that files a 20-F (its US shares are usually depositary receipts, which can stand for several ordinary shares),
gets a flag instead of ratios.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Live:
    name: str
    label: str
    description: str
    higher_is_better: bool = False


LIVE = {c.name: c for c in (
    Live("price", "Price", "Latest quote (or last close outside market hours) from the price provider.", True),
    Live("market_cap", "Market cap", "Price times split-adjusted common shares outstanding at the latest fiscal year end.", True),
    Live("pe", "P/E", "Price over the latest fiscal year's diluted EPS; empty when EPS is at or below zero."),
    Live("pb", "P/B", "Price over the latest fiscal year's book value per share; empty when book value is at or below zero."),
    Live("ptb", "P/tangible book", "Price over the latest fiscal year's tangible book value per share; empty when it is at or below zero."),
    Live("ps", "P/S", "Price over the latest fiscal year's revenue per share."),
    Live("pfcf", "P/FCF", "Price over the latest fiscal year's free cash flow per share; empty when FCF is at or below zero."),
    Live("earnings_yield", "Earnings yield", "Latest fiscal year's diluted EPS over price (negative for a loss).", True),
    Live("fcf_yield", "FCF yield", "Latest fiscal year's free cash flow per share over price.", True),
    Live("dividend_yield", "Dividend yield", "Latest fiscal year's dividends per share over price.", True),
    Live("ev_ebit", "EV/EBIT", "Enterprise value (market cap plus debt minus cash, either counted as zero when not reported) "
         "over the latest fiscal year's operating income; empty when operating income is at or below zero."),
    Live("fiscal_year", "Fiscal year", "The fiscal year whose fundamentals the live ratios use.", True),
)}
LIVE_COLUMNS = [f"live.{name}" for name in LIVE]
FUNDAMENTALS = ("eps", "bvps", "tbvps", "revenue_ps", "fcf_ps", "dps", "shares", "debt_ps", "cash_ps", "ebit_ps")
QUOTES_VIEW = "screen_quotes"


def live_sql() -> str:
    """CTEs `latest` and `live` (cik, price_flag, live.* columns), reading the quotes registered as QUOTES_VIEW."""
    pivots = ",\n    ".join(f"max(value) filter (where metric = '{m}') as {m}" for m in FUNDAMENTALS)
    ratios = {
        "price": "q.price",
        "market_cap": "q.price * l.shares",
        "pe": "case when l.eps > 0 then q.price / l.eps end",
        "pb": "case when l.bvps > 0 then q.price / l.bvps end",
        "ptb": "case when l.tbvps > 0 then q.price / l.tbvps end",
        "ps": "case when l.revenue_ps > 0 then q.price / l.revenue_ps end",
        "pfcf": "case when l.fcf_ps > 0 then q.price / l.fcf_ps end",
        "earnings_yield": "l.eps / q.price",
        "fcf_yield": "l.fcf_ps / q.price",
        "dividend_yield": "l.dps / q.price",
        "ev_ebit": "case when l.ebit_ps > 0 then (q.price + coalesce(l.debt_ps, 0) - coalesce(l.cash_ps, 0)) / l.ebit_ps end",
        "fiscal_year": "l.fiscal_year",
    }
    flag = ("case when c.currency is not null and q.currency is not null and c.currency <> q.currency "
            "then 'filings in ' || c.currency || ', price in ' || q.currency "
            "when c.latest_form like '20-F%' then 'files a 20-F: US shares may be depositary receipts' end")
    columns = ",\n    ".join(
        f'case when price_flag is null and q.price > 0 then {sql} end as "live.{name}"' for name, sql in ratios.items()
    )
    return f"""latest_year as (
  select cik, max(fiscal_year) as fiscal_year from metric_values group by cik
), latest as (
  select m.cik, y.fiscal_year,
    {pivots}
  from metric_values m join latest_year y on m.cik = y.cik and m.fiscal_year = y.fiscal_year
  group by m.cik, y.fiscal_year
), live as (
  select c.cik, flagged.price_flag,
    {columns}
  from companies c
  join {QUOTES_VIEW} q on upper(c.ticker) = q.ticker
  left join latest l on l.cik = c.cik
  cross join lateral (select {flag} as price_flag) flagged
)"""


def register_quotes(con: duckdb.DuckDBPyConnection, quotes: pd.DataFrame | None) -> None:
    frame = pd.DataFrame(columns=["ticker", "price", "currency"]) if quotes is None else quotes
    frame = frame.assign(ticker=frame["ticker"].astype(str).str.upper(), price=frame["price"].astype(float),
                         currency=frame["currency"].astype(object))[["ticker", "price", "currency"]]
    con.register(QUOTES_VIEW, frame)


def live_ratios(con: duckdb.DuckDBPyConnection, quotes: pd.DataFrame) -> pd.DataFrame:
    """One row per quoted company: ticker, price_flag, and the live.* columns."""
    register_quotes(con, quotes)
    try:
        return con.execute(f"with {live_sql()} select c.ticker, live.* exclude (cik) from live join companies c using (cik) "
                           "order by c.ticker").fetchdf()
    finally:
        con.unregister(QUOTES_VIEW)


HISTORICAL = {"pe": ("eps", "P/E"), "pb": ("bvps", "P/B"), "pfcf": ("fcf_ps", "P/FCF"), "dividend_yield": ("dps", "Dividend yield")}


def filing_date_prices(filings: pd.DataFrame, history: pd.DataFrame, max_days: int = 7) -> pd.Series:
    """Close on the date each fiscal year's numbers first became public, its first 10-K's filing date (the next
    trading day's close if it was filed on a day with no trading). Indexed by fiscal year; missing when no close
    is near or the first filing date is unknown."""
    closes = history.set_index(pd.to_datetime(history["date"]))["close"].sort_index()
    out = {}
    for row in filings.itertuples():
        if pd.isna(row.first_filed) or not row.first_filed:
            continue
        filed = pd.Timestamp(row.first_filed)
        after = closes[(closes.index >= filed) & (closes.index <= filed + pd.Timedelta(days=max_days))]
        out[int(row.fiscal_year)] = float(after.iloc[0]) if len(after) else np.nan
    return pd.Series(out, dtype=float).sort_index()


def historical_ratios(con: duckdb.DuckDBPyConnection, cik: int, history: pd.DataFrame) -> pd.DataFrame:
    """P/E, P/B, P/FCF, and dividend yield at each fiscal year, priced at the close on its 10-K filing date."""
    filings = con.execute("select fiscal_year, first_filed from filings where cik = ? order by fiscal_year", [cik]).fetchdf()
    values = con.execute("select fiscal_year, metric, value from metric_values where cik = ? and metric in (?, ?, ?, ?)",
                         [cik, *(m for m, _ in HISTORICAL.values())]).fetchdf()
    series = values.pivot(index="fiscal_year", columns="metric", values="value") if len(values) else pd.DataFrame()
    price = filing_date_prices(filings, history) if len(history) else pd.Series(dtype=float)
    frame = pd.DataFrame(index=sorted(set(filings["fiscal_year"]))).rename_axis("fiscal_year")
    frame["filed"] = filings.set_index("fiscal_year")["first_filed"]
    frame["price"] = price
    with np.errstate(all="ignore"):
        for name, (metric, _) in HISTORICAL.items():
            per_share = series[metric] if metric in series else pd.Series(np.nan, index=frame.index)
            per_share = per_share.reindex(frame.index)
            if name == "dividend_yield":
                frame[name] = per_share / frame["price"]
            else:
                frame[name] = (frame["price"] / per_share).where(per_share > 0)
    return frame.reset_index()


def ratio_ranges(historical: pd.DataFrame, live: dict[str, float] | None = None, years: int = 10) -> pd.DataFrame:
    """For each historical ratio: the low, median, and high over the latest `years` fiscal years with a value,
    next to today's live value."""
    rows = []
    for name, (_, label) in HISTORICAL.items():
        values = historical.dropna(subset=[name]).sort_values("fiscal_year")[name].tail(years) if name in historical else pd.Series(dtype=float)
        rows.append({"ratio": label, "years": len(values),
                     "low": values.min() if len(values) else np.nan, "median": values.median() if len(values) else np.nan,
                     "high": values.max() if len(values) else np.nan, "today": (live or {}).get(f"live.{name}", np.nan)})
    return pd.DataFrame(rows)
