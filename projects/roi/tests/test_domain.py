from datetime import date

import pytest

from roi.domain import (
    AssetKind,
    OptionContract,
    OptionRight,
    Order,
    OrderSide,
    Position,
    Security,
)


def test_equity_security_is_default() -> None:
    sec = Security("AAPL")
    assert sec.kind is AssetKind.EQUITY
    assert sec.option is None


def test_option_security_requires_contract() -> None:
    with pytest.raises(ValueError):
        Security("AAPL", kind=AssetKind.OPTION)


def test_equity_security_rejects_contract() -> None:
    contract = OptionContract("AAPL", date(2025, 1, 17), 200.0, OptionRight.CALL)
    with pytest.raises(ValueError):
        Security("AAPL", kind=AssetKind.EQUITY, option=contract)


def test_valid_option_security() -> None:
    contract = OptionContract("AAPL", date(2025, 1, 17), 200.0, OptionRight.CALL)
    sec = Security("AAPL250117C200", kind=AssetKind.OPTION, option=contract)
    assert sec.option is contract


def test_order_quantity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Order(Security("AAPL"), OrderSide.BUY, 0)


def test_position_cost_basis() -> None:
    pos = Position(Security("AAPL"), quantity=10, avg_price=150.0)
    assert pos.cost_basis == 1500.0
