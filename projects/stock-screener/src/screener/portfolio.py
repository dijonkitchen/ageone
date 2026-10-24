"""Portfolios: a plain-text TOML file of holdings, return assumptions, and Kelly settings, and its allocation.

See SPEC-2026-10-03-portfolio-kelly. Not investment advice: the allocation is the mathematical result of the
user's own return assumptions.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import tomli_w

from . import kelly
from .prices import today as _today
from .valuation import live_ratios

PORTFOLIO_DISCLAIMER = (
    "The allocation is the mathematical result of your own return assumptions. Kelly sizing is aggressive and "
    "assumes those assumptions are right; a fraction of Kelly lowers the risk of being wrong. Nothing here is "
    "investment advice."
)
METHODS = ("manual", "fcf", "earnings", "historical")
METHOD_LABELS = {
    "manual": "typed in",
    "fcf": "FCF yield plus capped FCF per share growth",
    "earnings": "earnings yield plus capped EPS growth",
    "historical": "mean price return over the lookback",
}
# Key 10-year metrics shown next to each holding.
KEY_METRICS = ("bvps.cagr", "eps.cagr", "fcf_ps.cagr", "roe.avg", "debt_to_equity.latest")


@dataclass
class Holding:
    ticker: str
    shares: float | None = None  # currently held, to show current weights and trades
    method: str = "manual"
    expected_return: float | None = None  # used when method is manual


@dataclass
class Settings:
    fraction: float = 0.5
    risk_free: float = 0.04
    max_total: float = 1.0  # above 1 allows leverage
    max_weight: float | None = None
    lookback_years: float = 5.0
    growth_cap: float = 0.10
    sensitivity: float = 0.02


@dataclass
class Portfolio:
    name: str = "Portfolio"
    value: float = 100_000.0
    holdings: list[Holding] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)

    def tickers(self) -> list[str]:
        return [h.ticker for h in self.holdings]

    def add(self, ticker: str) -> None:
        ticker = ticker.strip().upper()
        if ticker and ticker not in self.tickers():
            self.holdings.append(Holding(ticker))

    def remove(self, ticker: str) -> None:
        self.holdings = [h for h in self.holdings if h.ticker != ticker.upper()]

    # File format

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        raw = data.get("kelly", {})
        settings = Settings(**{k: raw[k] for k in asdict(Settings()) if k in raw})
        holdings = [Holding(h["ticker"].upper(), h.get("shares"), h.get("method", "manual"), h.get("expected_return"))
                    for h in data.get("holdings", [])]
        portfolio = cls(data.get("name", cls.name), float(data.get("value", cls.value)), holdings, settings)
        portfolio.validate()
        return portfolio

    @classmethod
    def loads(cls, text: str) -> Portfolio:
        return cls.from_dict(tomllib.loads(text))

    @classmethod
    def load(cls, path: Path | str) -> Portfolio:
        return cls.loads(Path(path).read_text())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "kelly": {k: v for k, v in asdict(self.settings).items() if v is not None},
            "holdings": [{k: v for k, v in asdict(h).items() if v is not None} for h in self.holdings],
        }

    def dumps(self) -> str:
        return tomli_w.dumps(self.to_dict())

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.dumps())

    def validate(self) -> None:
        s = self.settings
        if not 0 < s.fraction <= 1:
            raise ValueError("the Kelly fraction must be above 0 and at most 1")
        if s.max_total <= 0 or (s.max_weight is not None and s.max_weight <= 0):
            raise ValueError("max_total and max_weight must be above zero")
        for h in self.holdings:
            if h.method not in METHODS:
                raise ValueError(f"{h.ticker}: method must be one of {', '.join(METHODS)}")
            if h.method == "manual" and h.expected_return is None:
                raise ValueError(f"{h.ticker}: a manual method needs expected_return")


@dataclass
class View:
    """Everything the portfolio page and command show."""

    rows: pd.DataFrame  # per holding: live price and ratios, key metrics, suggested and used μ
    allocation: kelly.Allocation | None
    covariance: np.ndarray | None
    shrinkage: float | None
    days: int
    problems: list[str]


def suggestions(con: duckdb.DuckDBPyConnection, portfolio: Portfolio, live: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Each holding's suggested expected return by every method."""
    s = portfolio.settings
    growth = con.execute(
        "select upper(c.ticker) as ticker, s.metric, s.value from stats s join companies c using (cik) "
        "where s.\"window\" = '10' and s.stat = 'cagr' and s.metric in ('fcf_ps', 'eps')").fetchdf()
    growth = growth.pivot_table(index="ticker", columns="metric", values="value") if len(growth) else pd.DataFrame()
    live = live.set_index("ticker") if len(live) else pd.DataFrame()
    rows = []
    for h in portfolio.holdings:
        g = growth.loc[h.ticker] if h.ticker in growth.index else {}
        lv = live.loc[h.ticker] if h.ticker in live.index else {}
        rows.append({
            "ticker": h.ticker,
            "fcf": kelly.fundamentals_return(lv.get("live.fcf_yield", math.nan), g.get("fcf_ps", math.nan), s.growth_cap),
            "earnings": kelly.fundamentals_return(lv.get("live.earnings_yield", math.nan), g.get("eps", math.nan), s.growth_cap),
            "historical": kelly.historical_mean_return(history, h.ticker, s.lookback_years),
        })
    return pd.DataFrame(rows, columns=["ticker", "fcf", "earnings", "historical"])


def view(con: duckdb.DuckDBPyConnection, portfolio: Portfolio, quotes: pd.DataFrame, history: pd.DataFrame) -> View:
    """Live ratios, key metrics, return suggestions, and the Kelly allocation for a portfolio.

    quotes has a row per ticker (QUOTE_COLUMNS); history holds daily closes covering the lookback.
    """
    problems: list[str] = []
    tickers = portfolio.tickers()
    rows = pd.DataFrame({"ticker": tickers})
    quoted = quotes.assign(ticker=quotes["ticker"].str.upper()) if len(quotes) else pd.DataFrame(columns=["ticker", "price"])
    live = live_ratios(con, quoted) if len(quoted) else pd.DataFrame(columns=["ticker"])
    quote_cols = [c for c in ("ticker", "currency", "timestamp", "source", "realtime", "last_close") if c in quoted]
    rows = rows.merge(quoted[quote_cols], on="ticker", how="left").merge(live, on="ticker", how="left")
    metrics = con.execute(
        "select upper(c.ticker) as ticker, s.metric || '.' || s.stat as column, s.value from stats s join companies c using (cik) "
        "where s.\"window\" = '10'").fetchdf()
    metrics = metrics[metrics["column"].isin(KEY_METRICS)]
    if len(metrics):
        rows = rows.merge(metrics.pivot_table(index="ticker", columns="column", values="value").reset_index(), on="ticker", how="left")
    suggested = suggestions(con, portfolio, live, history)
    rows = rows.merge(suggested, on="ticker", how="left")
    used = []
    for h, row in zip(portfolio.holdings, rows.itertuples(index=False)):
        value = h.expected_return if h.method == "manual" else getattr(row, h.method)
        used.append(np.nan if value is None else value)
    rows["method"] = [h.method for h in portfolio.holdings]
    rows["mu"] = used
    rows["held"] = [h.shares for h in portfolio.holdings]

    if not tickers:
        return View(rows, None, None, None, 0, ["Add holdings to allocate."])
    for column, what in (("live.price", "live price"), ("mu", "expected return")):
        missing = rows.loc[rows[column].isna(), "ticker"].tolist() if column in rows else tickers
        if missing:
            problems.append(f"No {what} for {', '.join(missing)}.")
    flagged = rows.dropna(subset=["price_flag"]) if "price_flag" in rows else rows.iloc[0:0]
    problems.extend(f"{r.ticker}: {r.price_flag}." for r in flagged.itertuples())
    try:
        cov, shrinkage, days = kelly.covariance(history, tickers, portfolio.settings.lookback_years)
    except ValueError as error:
        return View(rows, None, None, None, 0, [*problems, str(error)])
    if problems:
        return View(rows, None, cov, shrinkage, days, problems)
    s = portfolio.settings
    allocation = kelly.allocate(
        tickers, rows["mu"].to_numpy(float), cov, rows["live.price"].to_numpy(float), s.risk_free, portfolio.value,
        s.fraction, kelly.Constraints(True, s.max_total, s.max_weight), rows["held"].tolist(), s.sensitivity)
    return View(rows, allocation, cov, shrinkage, days, problems)


def history_window(settings: Settings, today: date | None = None) -> tuple[date, date]:
    end = today or _today()
    return end - timedelta(days=round(365.25 * settings.lookback_years) + 7), end
