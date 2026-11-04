"""Comparable key stats and valuation ratios (Spec 0004).

Ratios with a zero denominator return ``None`` rather than raising, so a table
of mixed companies never blows up on one bad figure.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import Financials


def _safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


@dataclass(frozen=True, slots=True)
class KeyStats:
    symbol: str
    price: float
    market_cap: float
    enterprise_value: float
    pe: float | None
    ps: float | None
    pb: float | None
    ev_to_fcf: float | None
    fcf_yield: float | None
    net_margin: float | None
    roe: float | None
    debt_to_equity: float | None


def key_stats(financials: Financials, price: float) -> KeyStats:
    """Derive comparable stats from a company's financials and current price."""
    market_cap = price * financials.shares_outstanding
    enterprise_value = market_cap + financials.net_debt
    return KeyStats(
        symbol=financials.symbol,
        price=price,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        pe=_safe_div(market_cap, financials.net_income),
        ps=_safe_div(market_cap, financials.revenue),
        pb=_safe_div(market_cap, financials.shareholders_equity),
        ev_to_fcf=_safe_div(enterprise_value, financials.free_cash_flow),
        fcf_yield=_safe_div(financials.free_cash_flow, market_cap),
        net_margin=_safe_div(financials.net_income, financials.revenue),
        roe=_safe_div(financials.net_income, financials.shareholders_equity),
        debt_to_equity=_safe_div(financials.total_debt, financials.shareholders_equity),
    )
