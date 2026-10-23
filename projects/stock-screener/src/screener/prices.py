"""Prices: one small provider interface, an OpenBB adapter behind it, and a local cache of daily history.

See SPEC-2026-10-03-portfolio-kelly and the stack decision record. A provider returns tables with the
columns below; nothing else in the screener knows which provider it is.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

QUOTE_COLUMNS = ["ticker", "price", "currency", "timestamp", "source", "realtime", "last_close"]
HISTORY_COLUMNS = ["ticker", "date", "close"]
EASTERN = ZoneInfo("America/New_York")


class PriceProvider(Protocol):
    """Quotes and daily closes for a list of tickers.

    quote() returns QUOTE_COLUMNS: price, its currency, when it was quoted (UTC, naive), the source,
    whether it is real time (else delayed), and whether it is the last close (outside market hours).
    history() returns HISTORY_COLUMNS: daily closes adjusted for splits but not dividends, so they
    match split-adjusted per-share values.
    """

    name: str

    def quote(self, tickers: list[str]) -> pd.DataFrame: ...

    def history(self, tickers: list[str], start: date, end: date) -> pd.DataFrame: ...


def market_open(now: datetime) -> bool:
    """US regular trading hours, 9:30 to 16:00 Eastern on weekdays (exchange holidays not counted)."""
    local = now.replace(tzinfo=UTC).astimezone(EASTERN) if now.tzinfo is None else now.astimezone(EASTERN)
    return local.weekday() < 5 and time(9, 30) <= local.time() < time(16, 0)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def today() -> date:
    """Today in New York, where the exchanges are."""
    return datetime.now(EASTERN).date()


class OpenBBProvider:
    """Any OpenBB provider extension installed in the environment (yfinance by default, or fmp, polygon, ...).

    It calls the provider's fetchers for OpenBB's standard EquityQuote and EquityHistorical models directly,
    with the keys from config, so no OpenBB account or settings file is involved.
    """

    def __init__(self, provider: str = "yfinance", credentials: dict[str, str] | None = None, realtime: bool = False,
                 clock=_now):
        from importlib.metadata import entry_points

        found = {e.name: e for e in entry_points(group="openbb_provider_extension")}
        if provider not in found:
            raise SystemExit(f"OpenBB provider {provider!r} is not installed (have: {', '.join(sorted(found))}); "
                             f"add its extension, e.g. 'uv add openbb-{provider}'.")
        self._provider = found[provider].load()
        self.name = f"openbb/{provider}"
        self.credentials = credentials or {}
        self.realtime = realtime
        self.clock = clock

    def _fetcher(self, model: str):
        from importlib import import_module

        base = import_module(f"openbb_core.provider.standard_models.{model}")
        params = next(v for k, v in vars(base).items() if k.endswith("QueryParams") and getattr(v, "__module__", "") == base.__name__)
        for fetcher in self._provider.fetcher_dict.values():
            if issubclass(getattr(fetcher, "query_params_type", object), params):
                return fetcher
        raise SystemExit(f"{self.name} has no {model} data")

    def _fetch(self, model: str, params: dict) -> list:
        result = asyncio.run(self._fetcher(model).fetch_data(params, self.credentials))
        return list(getattr(result, "result", result) or [])

    def quote(self, tickers: list[str]) -> pd.DataFrame:
        now = self.clock()
        if now.tzinfo is not None:
            now = now.astimezone(UTC).replace(tzinfo=None)
        closed = not market_open(now)
        rows = []
        for item in self._fetch("equity_quote", {"symbol": ",".join(tickers)}):
            price = item.last_price if item.last_price is not None else item.prev_close
            stamp = getattr(item, "last_timestamp", None)
            rows.append({
                "ticker": item.symbol.upper(), "price": price, "currency": getattr(item, "currency", None),
                "timestamp": pd.Timestamp(stamp).tz_localize(None) if stamp else now, "source": self.name,
                "realtime": self.realtime and not closed, "last_close": closed,
            })
        return pd.DataFrame(rows, columns=QUOTE_COLUMNS)

    def history(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        frames = []
        for ticker in tickers:
            params = {"symbol": ticker, "start_date": start.isoformat(), "end_date": end.isoformat()}
            if "yfinance" in self.name:
                params["adjustment"] = "splits_only"
            rows = [{"ticker": ticker.upper(), "date": pd.Timestamp(r.date), "close": r.close} for r in self._fetch("equity_historical", params)]
            frames.append(pd.DataFrame(rows, columns=HISTORY_COLUMNS))
        return _frame(frames, HISTORY_COLUMNS)


class RecordedProvider:
    """Quotes and history from recorded files: for tests and for working offline.

    quotes.csv holds QUOTE_COLUMNS; history is one <TICKER>.prices.csv (date, close) per ticker.
    """

    def __init__(self, folder: Path | str, name: str = "recorded"):
        self.folder = Path(folder)
        self.name = name

    def quote(self, tickers: list[str]) -> pd.DataFrame:
        path = self.folder / "quotes.csv"
        quotes = pd.read_csv(path, parse_dates=["timestamp"]) if path.exists() else pd.DataFrame(columns=QUOTE_COLUMNS)
        wanted = {t.upper() for t in tickers}
        return quotes[quotes["ticker"].isin(wanted)].reset_index(drop=True)[QUOTE_COLUMNS]

    def history(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        frames = []
        for ticker in tickers:
            path = self.folder / f"{ticker.upper()}.prices.csv"
            if path.exists():
                frame = pd.read_csv(path, parse_dates=["date"]).assign(ticker=ticker.upper())
                frames.append(frame[(frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))])
        return _frame(frames, HISTORY_COLUMNS)


def _frame(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    frames = [f[columns] for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def from_config(prices) -> PriceProvider:
    return OpenBBProvider(prices.provider, prices.credentials, prices.realtime)


# Cache

CACHE_SCHEMA = """
create table if not exists history (ticker varchar, date date, close double, source varchar, primary key (ticker, date));
create table if not exists history_range (ticker varchar primary key, start date, "end" date, fetched_at timestamp);
create table if not exists quotes (
    ticker varchar primary key, price double, currency varchar, timestamp timestamp, source varchar,
    realtime boolean, last_close boolean
);
"""


class PriceCache:
    """Daily history and the last quote per ticker, in a DuckDB file of its own next to the screener's."""

    def __init__(self, path: Path | str, provider: PriceProvider | None = None):
        self.con = duckdb.connect(str(path))
        self.con.execute(CACHE_SCHEMA)
        self.provider = provider

    def close(self) -> None:
        self.con.close()

    def refresh_quotes(self, tickers: list[str]) -> pd.DataFrame:
        tickers = sorted({t.upper() for t in tickers if t})
        if tickers and self.provider is not None:
            fresh = self.provider.quote(tickers).dropna(subset=["price"])
            if len(fresh):
                self.con.execute(f"insert or replace into quotes select {', '.join(QUOTE_COLUMNS)} from fresh")
        return self.quotes(tickers)

    def quotes(self, tickers: list[str] | None = None) -> pd.DataFrame:
        frame = self.con.execute(f"select {', '.join(QUOTE_COLUMNS)} from quotes order by ticker").fetchdf()
        return frame if tickers is None else frame[frame["ticker"].isin({t.upper() for t in tickers})].reset_index(drop=True)

    def history(self, tickers: list[str], start: date, end: date, refetch_after: timedelta = timedelta(hours=12)) -> pd.DataFrame:
        """Daily closes from the cache, fetching only what it lacks: a range not covered yet, or a stale recent end."""
        tickers = sorted({t.upper() for t in tickers if t})
        if self.provider is not None:
            ranges = {r[0]: r[1:] for r in self.con.execute('select ticker, start, "end", fetched_at from history_range').fetchall()}
            now = _now()
            for ticker in tickers:
                have = ranges.get(ticker)
                stale = have and have[1] < end and now - have[2] > refetch_after
                if have and have[0] <= start and not stale:
                    continue
                lo = min(start, have[0]) if have else start
                fetched = self.provider.history([ticker], lo, end)
                fetched = fetched.assign(source=self.provider.name, date=pd.to_datetime(fetched["date"]).dt.date)
                self.con.execute("begin")
                self.con.execute("delete from history where ticker = ? and date between ? and ?", [ticker, lo, end])
                if len(fetched):
                    self.con.execute("insert or replace into history select ticker, date, close, source from fetched")
                self.con.execute("insert or replace into history_range values (?, ?, ?, ?)", [ticker, lo, max(end, have[1]) if have else end, now])
                self.con.execute("commit")
        if not tickers:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        frame = self.con.execute(
            f"select ticker, date, close from history where ticker in ({', '.join('?' * len(tickers))}) and date between ? and ? "
            "order by ticker, date", [*tickers, start, end]).fetchdf()
        frame["date"] = pd.to_datetime(frame["date"])
        return frame
