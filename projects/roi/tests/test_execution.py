import pytest

from roi.adapters import InMemoryMarketData
from roi.domain import Order, OrderSide, Security
from roi.execution import (
    InsufficientFunds,
    InsufficientHolding,
    PaperBroker,
    RiskLimitExceeded,
)

from .helpers import bars_from_closes

AAPL = Security("AAPL")


def broker(price: float = 100.0, **kw) -> PaperBroker:
    market = InMemoryMarketData({AAPL: bars_from_closes([price])})
    return PaperBroker(market, **kw)


@pytest.mark.criteria("TRD-1")
def test_buy_then_sell_round_trip() -> None:
    b = broker(price=100.0, starting_cash=1000.0)
    b.submit(Order(AAPL, OrderSide.BUY, 5))
    assert b.cash == 500.0
    pos = b.position(AAPL)
    assert pos is not None and pos.quantity == 5 and pos.avg_price == 100.0
    b.submit(Order(AAPL, OrderSide.SELL, 5))
    assert b.cash == 1000.0
    assert b.position(AAPL) is None


def test_buy_averages_price() -> None:
    market = InMemoryMarketData({AAPL: bars_from_closes([100.0])})
    b = PaperBroker(market, starting_cash=10_000.0)
    b.submit(Order(AAPL, OrderSide.BUY, 10))  # @100
    # bump price and buy again
    market2 = InMemoryMarketData({AAPL: bars_from_closes([200.0])})
    b._prices = market2
    b.submit(Order(AAPL, OrderSide.BUY, 10))  # @200
    pos = b.position(AAPL)
    assert pos is not None and pos.quantity == 20
    assert pos.avg_price == pytest.approx(150.0)


@pytest.mark.criteria("TRD-2")
def test_insufficient_funds_rejected_and_state_unchanged() -> None:
    b = broker(price=100.0, starting_cash=50.0)
    with pytest.raises(InsufficientFunds):
        b.submit(Order(AAPL, OrderSide.BUY, 1))
    assert b.cash == 50.0
    assert b.position(AAPL) is None


@pytest.mark.criteria("TRD-2")
def test_insufficient_holding_rejected() -> None:
    b = broker(price=100.0, starting_cash=1000.0)
    with pytest.raises(InsufficientHolding):
        b.submit(Order(AAPL, OrderSide.SELL, 1))


@pytest.mark.criteria("TRD-2")
def test_risk_limit_rejected() -> None:
    b = broker(price=100.0, starting_cash=10_000.0, max_position_value=500.0)
    with pytest.raises(RiskLimitExceeded):
        b.submit(Order(AAPL, OrderSide.BUY, 6))  # 600 > 500
    assert b.position(AAPL) is None


@pytest.mark.criteria("TRD-1")
def test_equity_conserved_on_fill() -> None:
    b = broker(price=100.0, starting_cash=1000.0)
    before = b.equity()
    b.submit(Order(AAPL, OrderSide.BUY, 5))
    # cash down 500, position worth 500 at same price -> equity unchanged
    assert b.equity() == pytest.approx(before)
