from datetime import UTC, date, datetime

import pandas as pd
import pytest
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalQueryParams,
)
from openbb_core.provider.standard_models.equity_quote import EquityQuoteQueryParams

from screener import prices


def test_market_hours():
    assert prices.market_open(datetime(2026, 10, 19, 15, 0, tzinfo=UTC))  # Monday 11:00 New York (UTC naive)
    assert not prices.market_open(datetime(2026, 10, 19, 21, 0, tzinfo=UTC))  # 17:00 New York
    assert not prices.market_open(datetime(2026, 10, 24, 15, 0, tzinfo=UTC))  # Saturday


def test_last_close_time():
    assert prices.last_close_time(datetime(2026, 10, 24, 5, 4, tzinfo=UTC)) == pd.Timestamp("2026-10-23 20:00")  # Saturday: Friday's close
    assert prices.last_close_time(datetime(2026, 10, 19, 15, 0, tzinfo=UTC)) == pd.Timestamp("2026-10-16 20:00")  # Monday open: Friday's
    assert prices.last_close_time(datetime(2026, 10, 20, 21, 0, tzinfo=UTC)) == pd.Timestamp("2026-10-20 20:00")  # Tuesday 17:00: today's
    assert prices.last_close_time(datetime(2026, 12, 1, 22, 0, tzinfo=UTC)) == pd.Timestamp("2026-12-01 21:00")  # standard time: 21:00 UTC


def test_quote_timestamps():
    class Fetcher:
        query_params_type = EquityQuoteQueryParams

        @staticmethod
        async def fetch_data(params, credentials=None):
            return items

    adapter = prices.OpenBBProvider.__new__(prices.OpenBBProvider)
    adapter._provider = Item(fetcher_dict={"Quote": Fetcher})
    adapter.name, adapter.credentials, adapter.realtime = "openbb/fake", {}, False
    adapter.clock = lambda: datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # Tuesday 11:00 New York, market open
    items = [
        Item(symbol="a", last_price=10.0, prev_close=9.0, last_timestamp=None, currency="USD"),
        Item(symbol="b", last_price=10.0, prev_close=9.0, last_timestamp=datetime(2026, 10, 20, 10, 59, tzinfo=prices.EASTERN), currency="USD"),
        Item(symbol="c", last_price=None, prev_close=9.0, last_timestamp=None, currency="USD"),
    ]
    stamps = adapter.quote(["A", "B", "C"]).set_index("ticker")["timestamp"]
    assert stamps["A"] == pd.Timestamp("2026-10-20 15:00")  # live with no quote time: when fetched
    assert stamps["B"] == pd.Timestamp("2026-10-20 14:59")  # a zoned quote time, converted to UTC
    assert stamps["C"] == pd.Timestamp("2026-10-19 20:00")  # previous close: Monday's close


def test_recorded_provider(prices_dir):
    provider = prices.RecordedProvider(prices_dir)
    quotes = provider.quote(["fast", "BLK", "NOPE"])
    assert sorted(quotes["ticker"]) == ["BLK", "FAST"]
    assert list(quotes.columns) == prices.QUOTE_COLUMNS
    history = provider.history(["FAST"], date(2020, 1, 1), date(2020, 1, 31))
    assert list(history.columns) == prices.HISTORY_COLUMNS and len(history) == 23


class Counting:
    def __init__(self, inner):
        self.inner, self.name, self.calls = inner, inner.name, []

    def quote(self, tickers):
        self.calls.append(("quote", tuple(tickers)))
        return self.inner.quote(tickers)

    def history(self, tickers, start, end):
        self.calls.append(("history", tuple(tickers), start, end))
        return self.inner.history(tickers, start, end)


def test_cache_fetches_history_once_and_extends_earlier(prices_dir, tmp_path):
    provider = Counting(prices.RecordedProvider(prices_dir))
    cache = prices.PriceCache(tmp_path / "p.duckdb", provider)
    first = cache.history(["FAST", "SLOW"], date(2020, 1, 1), date(2020, 12, 31))
    again = cache.history(["FAST", "SLOW"], date(2020, 6, 1), date(2020, 12, 31))
    assert len([c for c in provider.calls if c[0] == "history"]) == 2
    assert len(again) < len(first) and set(again["ticker"]) == {"FAST", "SLOW"}
    cache.history(["FAST"], date(2019, 1, 1), date(2020, 12, 31))
    assert provider.calls[-1] == ("history", ("FAST",), date(2019, 1, 1), date(2020, 12, 31))
    quotes = cache.refresh_quotes(["FAST"])
    assert quotes["price"].tolist() == [50.0] and cache.quotes()["ticker"].tolist() == ["FAST"]
    cache.close()
    # Reopened without a provider (offline), the cache still answers.
    assert len(prices.PriceCache(tmp_path / "p.duckdb").history(["FAST"], date(2019, 1, 1), date(2020, 12, 31))) > 400


class Item:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_openbb_adapter_uses_the_providers_standard_fetchers():
    class QuoteParams(EquityQuoteQueryParams):
        pass

    class HistoryParams(EquityHistoricalQueryParams):
        pass

    seen = []

    class QuoteFetcher:
        query_params_type = QuoteParams

        @staticmethod
        async def fetch_data(params, credentials=None):
            seen.append((params, credentials))
            return [Item(symbol="ko", last_price=None, prev_close=61.5, last_timestamp=None, currency="USD")]

    class HistoryFetcher:
        query_params_type = HistoryParams

        @staticmethod
        async def fetch_data(params, credentials=None):
            seen.append((params, credentials))
            return [Item(date=date(2024, 1, 2), close=60.0), Item(date=date(2024, 1, 3), close=60.5)]

    adapter = prices.OpenBBProvider.__new__(prices.OpenBBProvider)
    adapter._provider = Item(fetcher_dict={"Quote": QuoteFetcher, "History": HistoryFetcher})
    adapter.name, adapter.credentials, adapter.realtime = "openbb/fake", {"fake_api_key": "k"}, True
    adapter.clock = lambda: datetime(2026, 10, 24, 15, 0, tzinfo=UTC)  # Saturday: the last close
    quote = adapter.quote(["KO"]).iloc[0]
    assert (quote["ticker"], quote["price"], quote["source"]) == ("KO", 61.5, "openbb/fake")
    assert quote["last_close"] and not quote["realtime"]
    assert quote["timestamp"] == pd.Timestamp("2026-10-23 20:00")  # Friday's 16:00 New York close, not the fetch time
    history = adapter.history(["KO"], date(2024, 1, 1), date(2024, 1, 5))
    assert history["close"].tolist() == [60.0, 60.5]
    assert seen[0] == ({"symbol": "KO"}, {"fake_api_key": "k"})
    assert seen[1][0] == {"symbol": "KO", "start_date": "2024-01-01", "end_date": "2024-01-05"}


def test_missing_provider_says_how_to_install():
    with pytest.raises(SystemExit, match="uv add openbb-nope"):
        prices.OpenBBProvider("nope")
