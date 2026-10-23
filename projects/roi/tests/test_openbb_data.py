"""OpenBB adapter tests run fully offline via an injected fake client."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from roi.adapters import OpenBBMarketData
from roi.domain import Security


def fake_obb(rows_by_symbol):
    """Mimic the ``obb.equity.price.historical(...).results`` call chain."""

    def historical(symbol, start_date=None, end_date=None, provider=None):
        return SimpleNamespace(results=rows_by_symbol[symbol])

    return SimpleNamespace(
        equity=SimpleNamespace(price=SimpleNamespace(historical=historical))
    )


def row(d, o, h, low, c, v):
    return SimpleNamespace(date=d, open=o, high=h, low=low, close=c, volume=v)


AAPL = Security("AAPL")


@pytest.mark.criteria("DATA-1")
def test_maps_results_to_bars_in_chronological_order() -> None:
    # Provided out of order to prove the adapter sorts.
    client = fake_obb(
        {
            "AAPL": [
                row(date(2024, 1, 2), 11, 12, 10, 11.5, 2_000),
                row(date(2024, 1, 1), 10, 11, 9, 10.5, 1_000),
            ]
        }
    )
    md = OpenBBMarketData([AAPL], client=client)
    bars = md.history(AAPL)
    assert [b.ts for b in bars] == [datetime(2024, 1, 1), datetime(2024, 1, 2)]
    assert bars[0].close == 10.5 and bars[0].volume == 1_000
    assert md.latest(AAPL).close == 11.5


def test_history_limit_and_universe() -> None:
    client = fake_obb(
        {"AAPL": [row(date(2024, 1, i + 1), 1, 1, 1, float(i), 1) for i in range(5)]}
    )
    md = OpenBBMarketData([AAPL], client=client)
    assert len(md.history(AAPL, limit=2)) == 2
    assert [s.symbol for s in md.universe()] == ["AAPL"]


def test_accepts_string_and_datetime_dates() -> None:
    client = fake_obb(
        {
            "AAPL": [
                row("2024-01-01", 1, 1, 1, 1.0, 1),
                row(datetime(2024, 1, 2, 16, 0), 1, 1, 1, 2.0, 1),
            ]
        }
    )
    md = OpenBBMarketData([AAPL], client=client)
    bars = md.history(AAPL)
    assert bars[0].ts == datetime(2024, 1, 1)
    assert bars[1].ts == datetime(2024, 1, 2, 16, 0)


def test_results_are_cached_single_fetch() -> None:
    calls = {"n": 0}

    def historical(symbol, **kw):
        calls["n"] += 1
        return SimpleNamespace(results=[row(date(2024, 1, 1), 1, 1, 1, 1.0, 1)])

    client = SimpleNamespace(
        equity=SimpleNamespace(price=SimpleNamespace(historical=historical))
    )
    md = OpenBBMarketData([AAPL], client=client)
    md.history(AAPL)
    md.latest(AAPL)
    assert calls["n"] == 1


def test_requires_at_least_one_security() -> None:
    with pytest.raises(ValueError):
        OpenBBMarketData([])
