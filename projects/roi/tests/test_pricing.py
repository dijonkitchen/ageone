from datetime import date

import pytest

from roi.domain import OptionRight
from roi.pricing import (
    black_scholes_price,
    implied_volatility,
    put_call_parity_residual,
    time_to_expiry,
)

CALL = OptionRight.CALL
PUT = OptionRight.PUT


def test_time_to_expiry() -> None:
    assert time_to_expiry(date(2025, 1, 1), date(2024, 1, 1)) == pytest.approx(
        366 / 365
    )


@pytest.mark.criteria("OPT-1")
def test_black_scholes_atm_call_known_value() -> None:
    # S=K=100, r=0, vol=20%, T=1 -> ~7.96
    price = black_scholes_price(100, 100, 1.0, 0.0, 0.20, CALL)
    assert price == pytest.approx(7.96, abs=0.02)


def test_atm_call_equals_put_when_rate_zero() -> None:
    call = black_scholes_price(100, 100, 1.0, 0.0, 0.20, CALL)
    put = black_scholes_price(100, 100, 1.0, 0.0, 0.20, PUT)
    assert call == pytest.approx(put)  # parity with r=0, S=K


@pytest.mark.criteria("OPT-1")
def test_model_prices_satisfy_put_call_parity() -> None:
    call = black_scholes_price(100, 90, 0.5, 0.03, 0.25, CALL)
    put = black_scholes_price(100, 90, 0.5, 0.03, 0.25, PUT)
    residual = put_call_parity_residual(call, put, 100, 90, 0.5, 0.03)
    assert residual == pytest.approx(0.0, abs=1e-9)


def test_expired_option_is_intrinsic() -> None:
    assert black_scholes_price(120, 100, 0.0, 0.05, 0.3, CALL) == 20.0
    assert black_scholes_price(80, 100, -1.0, 0.05, 0.3, PUT) == 20.0


def test_negative_volatility_rejected() -> None:
    with pytest.raises(ValueError):
        black_scholes_price(100, 100, 1.0, 0.0, 0.0, CALL)


@pytest.mark.criteria("OPT-2")
def test_implied_volatility_round_trip() -> None:
    price = black_scholes_price(100, 105, 0.75, 0.02, 0.32, CALL)
    iv = implied_volatility(price, 100, 105, 0.75, 0.02, CALL)
    assert iv == pytest.approx(0.32, abs=1e-3)


@pytest.mark.criteria("OPT-2")
def test_implied_volatility_unattainable_returns_none() -> None:
    # A price below intrinsic cannot be reproduced by any volatility.
    assert implied_volatility(0.5, 120, 100, 1.0, 0.0, CALL) is None
    assert implied_volatility(5.0, 100, 100, 0.0, 0.0, CALL) is None  # expired
