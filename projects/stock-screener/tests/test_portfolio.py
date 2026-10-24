from datetime import date

import numpy as np
import pytest

from screener import portfolio as pf
from screener import prices

FILE = """
name = "Test"
value = 100000.0

[kelly]
fraction = 0.5
risk_free = 0.03
max_total = 1.0
max_weight = 0.6
lookback_years = 5.0
growth_cap = 0.1
sensitivity = 0.02

[[holdings]]
ticker = "FAST"
shares = 100.0
method = "manual"
expected_return = 0.14

[[holdings]]
ticker = "SLOW"
method = "historical"

[[holdings]]
ticker = "BLK"
method = "fcf"
"""


def inputs(book, prices_dir):
    provider = prices.RecordedProvider(prices_dir)
    quotes = provider.quote(book.tickers())
    start, end = pf.history_window(book.settings, date(2025, 6, 30))
    return quotes, provider.history(book.tickers(), start, end)


def test_file_round_trip_and_validation():
    book = pf.Portfolio.loads(FILE)
    assert pf.Portfolio.loads(book.dumps()) == book
    assert book.holdings[0].shares == 100 and book.settings.max_weight == 0.6
    book.add("ko")
    book.add("KO")
    book.remove("SLOW")
    assert book.tickers() == ["FAST", "BLK", "KO"]
    with pytest.raises(ValueError, match="manual method needs"):
        pf.Portfolio.loads('[[holdings]]\nticker = "X"\n')
    with pytest.raises(ValueError, match="fraction"):
        pf.Portfolio.loads("[kelly]\nfraction = 2.0\n")


def test_view_allocates_with_constraints(con, prices_dir):
    book = pf.Portfolio.loads(FILE)
    quotes, history = inputs(book, prices_dir)
    result = pf.view(con, book, quotes, history)
    assert result.problems == []
    rows = result.rows.set_index("ticker")
    assert rows.loc["FAST", "mu"] == 0.14
    assert rows.loc["SLOW", "mu"] == pytest.approx(rows.loc["SLOW", "historical"])
    assert rows.loc["BLK", "mu"] == pytest.approx(rows.loc["BLK", "live.fcf_yield"] + min(rows.loc["BLK", "fcf_ps.cagr"], 0.1))
    assert rows.loc["FAST", "bvps.cagr"] > 0.15
    a = result.allocation
    w = a.holdings.set_index("ticker")["weight"]
    assert (w >= 0).all() and w.sum() <= 1 + 1e-9 and (w <= 0.6 + 1e-9).all()
    assert (a.holdings["shares"] == np.floor(a.holdings["dollars"] / a.holdings["price"])).all()
    assert a.holdings.set_index("ticker").loc["FAST", "trade"] == a.holdings.set_index("ticker").loc["FAST", "shares"] - 100
    assert a.cash == pytest.approx(book.value - a.invested)
    # Deterministic: the same prices, filings, and file give the same allocation.
    again = pf.view(con, pf.Portfolio.loads(FILE), quotes, history).allocation
    assert again.holdings["weight"].tolist() == a.holdings["weight"].tolist()


def test_view_reports_what_is_missing(con, prices_dir):
    book = pf.Portfolio.loads(FILE)
    book.add("NOPE")
    quotes, history = inputs(book, prices_dir)
    result = pf.view(con, book, quotes, history)
    assert result.allocation is None
    assert "No live price for NOPE." in result.problems
