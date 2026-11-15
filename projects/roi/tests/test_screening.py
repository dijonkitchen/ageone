import pytest

from roi.domain import Security
from roi.screening import (
    AboveSMA,
    MinAvgVolume,
    PositiveMomentum,
    PriceBetween,
    Screener,
    Snapshot,
    all_of,
    any_of,
    negate,
)

from .helpers import bars_from_closes


def snap(symbol: str, closes, **kw) -> Snapshot:
    return Snapshot(Security(symbol), bars_from_closes(closes, **kw))


@pytest.mark.criteria("SCR-1")
def test_snapshot_requires_bars() -> None:
    with pytest.raises(ValueError):
        Snapshot(Security("X"), [])


def test_derived_metrics() -> None:
    s = snap("X", [10, 20, 30, 40])
    assert s.price == 40
    assert s.sma(2) == 35.0
    assert s.momentum(3) == pytest.approx(40 / 10 - 1)


@pytest.mark.criteria("SCR-1")
def test_metric_needs_enough_bars() -> None:
    s = snap("X", [10, 20])
    with pytest.raises(ValueError):
        s.sma(5)


@pytest.mark.criteria("SCR-3")
def test_filters() -> None:
    s = snap("X", [10, 11, 12, 13, 14])
    assert PriceBetween(10, 20)(s)
    assert not PriceBetween(0, 5)(s)
    assert MinAvgVolume(500_000, window=3)(s)
    assert AboveSMA(3)(s)
    assert PositiveMomentum(3)(s)


@pytest.mark.criteria("SCR-2")
def test_combinators() -> None:
    s = snap("X", [10, 11, 12])
    assert all_of()(s) is True  # vacuously true
    assert any_of()(s) is False  # vacuously false
    assert all_of(PriceBetween(0, 100), AboveSMA(2))(s)
    assert any_of(PriceBetween(0, 1), AboveSMA(2))(s)
    assert negate(PriceBetween(0, 1))(s)


@pytest.mark.criteria("SCR-5")
def test_filters_do_not_mutate_snapshot() -> None:
    s = snap("X", [10, 11, 12])
    before = tuple(s.bars)
    PositiveMomentum(2)(s)
    assert tuple(s.bars) == before


@pytest.mark.criteria("SCR-3", "SCR-4")
def test_screener_filters_and_ranks() -> None:
    rising = snap("UP", [10, 11, 12, 13, 14])
    falling = snap("DOWN", [14, 13, 12, 11, 10])
    screener = Screener(
        filters=[PositiveMomentum(3)],
        score=lambda s: s.momentum(3),
    )
    results = screener.run([rising, falling])
    assert [r.security.symbol for r in results] == ["UP"]


@pytest.mark.criteria("SCR-4")
def test_screener_stable_sort_on_ties() -> None:
    a = snap("A", [10, 10, 10])
    b = snap("B", [10, 10, 10])
    screener = Screener(score=lambda s: 0.0)
    results = screener.run([a, b])
    assert [r.security.symbol for r in results] == ["A", "B"]
