"""European option pricing and stock/option alignment checks (Spec 0005).

Pure and dependency-free: the normal distribution comes from the standard
library (`statistics.NormalDist`). Covers Black–Scholes pricing, an implied-
volatility solver, and a put–call parity scan that flags option quotes that are
inconsistent with the underlying.

Scope is European options with a continuous dividend yield. American exercise,
binomial trees, and a full greeks suite are future work (Spec 0005 non-goals).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import NormalDist

from .domain import OptionQuote, OptionRight

_N = NormalDist()
DAYS_PER_YEAR = 365.0


def time_to_expiry(expiry: date, asof: date) -> float:
    """Year fraction (ACT/365) between ``asof`` and ``expiry``."""
    return (expiry - asof).days / DAYS_PER_YEAR


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    right: OptionRight,
    *,
    dividend_yield: float = 0.0,
) -> float:
    """Black–Scholes–Merton price of a European option."""
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    t = time_to_expiry
    if t <= 0:  # expired: worth its intrinsic value
        intrinsic = spot - strike if right is OptionRight.CALL else strike - spot
        return max(intrinsic, 0.0)
    if volatility <= 0:
        raise ValueError("volatility must be positive")

    vol_root_t = volatility * math.sqrt(t)
    d1 = (
        math.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility**2) * t
    ) / vol_root_t
    d2 = d1 - vol_root_t
    discounted_spot = spot * math.exp(-dividend_yield * t)
    discounted_strike = strike * math.exp(-rate * t)
    if right is OptionRight.CALL:
        return discounted_spot * _N.cdf(d1) - discounted_strike * _N.cdf(d2)
    return discounted_strike * _N.cdf(-d2) - discounted_spot * _N.cdf(-d1)


def put_call_parity_residual(
    call_price: float,
    put_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    *,
    dividend_yield: float = 0.0,
) -> float:
    """``C - P - (S e^{-qT} - K e^{-rT})``; ~0 when call and put are aligned."""
    t = time_to_expiry
    forward = spot * math.exp(-dividend_yield * t) - strike * math.exp(-rate * t)
    return call_price - put_price - forward


def implied_volatility(
    price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    right: OptionRight,
    *,
    dividend_yield: float = 0.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """Solve for the volatility that reproduces ``price`` (bisection).

    Returns ``None`` when the price is unattainable (below intrinsic, or beyond
    a 500% vol), since Black–Scholes is monotonic in volatility.
    """
    t = time_to_expiry
    if t <= 0 or price <= 0:
        return None

    def diff(vol: float) -> float:
        return (
            black_scholes_price(
                spot, strike, t, rate, vol, right, dividend_yield=dividend_yield
            )
            - price
        )

    lo, hi = 1e-4, 5.0
    if diff(lo) > 0 or diff(hi) < 0:
        return None  # price not bracketed by the search range

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        residual = diff(mid)
        if abs(residual) < tol:
            return mid
        if residual < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@dataclass(frozen=True, slots=True)
class ParityResult:
    underlying: str
    strike: float
    expiry: date
    call_mid: float
    put_mid: float
    residual: float
    aligned: bool


def parity_scan(
    quotes: Iterable[OptionQuote],
    *,
    spot: float,
    rate: float,
    asof: date,
    tolerance: float,
    dividend_yield: float = 0.0,
) -> list[ParityResult]:
    """Pair calls and puts by (expiry, strike) and flag parity violations.

    A residual larger than ``tolerance`` (in price units) means the call, put,
    and underlying are not mutually consistent — a stale quote or a mispricing.
    """
    calls: dict[tuple[date, float], OptionQuote] = {}
    puts: dict[tuple[date, float], OptionQuote] = {}
    for quote in quotes:
        contract = quote.contract
        key = (contract.expiry, contract.strike)
        (calls if contract.right is OptionRight.CALL else puts)[key] = quote

    results: list[ParityResult] = []
    for expiry, strike in sorted(calls.keys() & puts.keys()):
        call, put = calls[(expiry, strike)], puts[(expiry, strike)]
        residual = put_call_parity_residual(
            call.mid,
            put.mid,
            spot,
            strike,
            time_to_expiry(expiry, asof),
            rate,
            dividend_yield=dividend_yield,
        )
        results.append(
            ParityResult(
                underlying=call.contract.underlying,
                strike=strike,
                expiry=expiry,
                call_mid=call.mid,
                put_mid=put.mid,
                residual=residual,
                aligned=abs(residual) <= tolerance,
            )
        )
    return results


def parity_violations(results: Sequence[ParityResult]) -> list[ParityResult]:
    """Just the misaligned rows from a :func:`parity_scan`."""
    return [r for r in results if not r.aligned]
