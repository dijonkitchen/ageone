"""A simple two-stage discounted cash flow model (Spec 0004).

Explicit free-cash-flow growth for N years, then a Gordon-growth terminal
value, all discounted to present. Enterprise value less net debt gives equity
value; divided by shares gives intrinsic value per share.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import Financials


@dataclass(frozen=True, slots=True)
class DCFAssumptions:
    growth_rate: float = 0.08  # explicit-period annual FCF growth
    years: int = 10
    discount_rate: float = 0.10  # WACC / required return
    terminal_growth: float = 0.025  # perpetual growth after the explicit period

    def __post_init__(self) -> None:
        if self.years <= 0:
            raise ValueError("years must be positive")
        if self.discount_rate <= self.terminal_growth:
            raise ValueError("discount_rate must exceed terminal_growth")


@dataclass(frozen=True, slots=True)
class DCFResult:
    enterprise_value: float
    equity_value: float
    intrinsic_value_per_share: float
    pv_explicit: float
    pv_terminal: float


def dcf(
    fcf0: float,
    shares_outstanding: float,
    net_debt: float,
    assumptions: DCFAssumptions | None = None,
) -> DCFResult:
    """Value a stream starting from base free cash flow ``fcf0``."""
    a = assumptions or DCFAssumptions()
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    r, g, tg = a.discount_rate, a.growth_rate, a.terminal_growth

    pv_explicit = 0.0
    for t in range(1, a.years + 1):
        fcf_t = fcf0 * (1 + g) ** t
        pv_explicit += fcf_t / (1 + r) ** t

    fcf_terminal = fcf0 * (1 + g) ** a.years * (1 + tg)
    terminal_value = fcf_terminal / (r - tg)
    pv_terminal = terminal_value / (1 + r) ** a.years

    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - net_debt
    return DCFResult(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        intrinsic_value_per_share=equity_value / shares_outstanding,
        pv_explicit=pv_explicit,
        pv_terminal=pv_terminal,
    )


def dcf_from_financials(
    financials: Financials, assumptions: DCFAssumptions | None = None
) -> DCFResult:
    """Run the DCF using a company's free cash flow, net debt, and shares."""
    return dcf(
        fcf0=financials.free_cash_flow,
        shares_outstanding=financials.shares_outstanding,
        net_debt=financials.net_debt,
        assumptions=assumptions,
    )
