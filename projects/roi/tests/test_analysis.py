from datetime import date

import pytest

from roi.adapters import InMemoryMarketData
from roi.analysis import (
    AssetEstimate,
    DCFAssumptions,
    analyze,
    annualized_volatility,
    dcf,
    dcf_from_financials,
    kelly_allocations,
    kelly_estimates,
    kelly_fraction,
    key_stats,
)
from roi.analysis.kelly import gross_exposure
from roi.domain import Financials, Security

from .helpers import bars_from_closes


def make_financials(symbol="X", **overrides) -> Financials:
    base = {
        "symbol": symbol,
        "period_end": date(2023, 12, 31),
        "revenue": 1000.0,
        "net_income": 100.0,
        "operating_cash_flow": 150.0,
        "capital_expenditures": 50.0,
        "total_debt": 200.0,
        "cash_and_equivalents": 80.0,
        "shareholders_equity": 500.0,
        "shares_outstanding": 10.0,
    }
    base.update(overrides)
    return Financials(**base)


# --- domain.Financials -----------------------------------------------------


def test_financials_derived_metrics() -> None:
    fin = make_financials()
    assert fin.free_cash_flow == 100.0  # 150 - 50
    assert fin.net_debt == 120.0  # 200 - 80
    assert fin.eps == 10.0  # 100 / 10


def test_financials_requires_shares() -> None:
    with pytest.raises(ValueError):
        make_financials(shares_outstanding=0)


# --- DCF -------------------------------------------------------------------


@pytest.mark.criteria("FUN-2")
def test_dcf_hand_computed() -> None:
    # fcf0=100, no growth, 1 year, r=10%, no terminal growth, 10 shares.
    result = dcf(
        fcf0=100.0,
        shares_outstanding=10.0,
        net_debt=0.0,
        assumptions=DCFAssumptions(
            growth_rate=0.0, years=1, discount_rate=0.10, terminal_growth=0.0
        ),
    )
    assert result.enterprise_value == pytest.approx(1000.0)
    assert result.intrinsic_value_per_share == pytest.approx(100.0)


def test_dcf_subtracts_net_debt() -> None:
    a = DCFAssumptions(
        growth_rate=0.0, years=1, discount_rate=0.10, terminal_growth=0.0
    )
    result = dcf(100.0, 10.0, net_debt=500.0, assumptions=a)
    assert result.equity_value == pytest.approx(500.0)
    assert result.intrinsic_value_per_share == pytest.approx(50.0)


@pytest.mark.criteria("FUN-2")
def test_dcf_rejects_bad_assumptions() -> None:
    with pytest.raises(ValueError):
        DCFAssumptions(discount_rate=0.02, terminal_growth=0.05)
    with pytest.raises(ValueError):
        DCFAssumptions(years=0)


def test_dcf_from_financials_uses_fcf_and_net_debt() -> None:
    fin = make_financials()
    assert dcf_from_financials(fin).intrinsic_value_per_share > 0


# --- ratios ----------------------------------------------------------------


def test_key_stats() -> None:
    fin = make_financials()
    stats = key_stats(fin, price=200.0)
    assert stats.market_cap == 2000.0  # 200 * 10
    assert stats.enterprise_value == pytest.approx(2120.0)  # + net debt 120
    assert stats.pe == pytest.approx(20.0)  # 2000 / 100
    assert stats.ps == pytest.approx(2.0)
    assert stats.fcf_yield == pytest.approx(0.05)  # 100 / 2000


@pytest.mark.criteria("FUN-3")
def test_ratios_none_on_zero_denominator() -> None:
    fin = make_financials(net_income=0.0)
    stats = key_stats(fin, price=200.0)
    assert stats.pe is None
    assert stats.net_margin == 0.0  # 0 / 1000 is a valid 0, not a crash


# --- Kelly -----------------------------------------------------------------


def test_kelly_fraction() -> None:
    assert kelly_fraction(0.1, 0.2) == pytest.approx(2.5)  # 0.1 / 0.04
    with pytest.raises(ValueError):
        kelly_fraction(0.1, 0.0)


@pytest.mark.criteria("FUN-4")
def test_kelly_allocations_half_kelly_and_amounts() -> None:
    estimates = [
        AssetEstimate("A", expected_return=0.2, volatility=0.4),  # f=1.25 -> 0.625
        AssetEstimate("B", expected_return=0.1, volatility=0.5),  # f=0.4  -> 0.20
    ]
    allocs = {a.symbol: a for a in kelly_allocations(estimates, total=10_000)}
    assert allocs["A"].weight == pytest.approx(0.625)
    assert allocs["A"].amount == pytest.approx(6250.0)
    assert allocs["B"].amount == pytest.approx(2000.0)


@pytest.mark.criteria("FUN-4")
def test_kelly_is_long_only_by_default() -> None:
    allocs = kelly_allocations(
        [AssetEstimate("A", expected_return=-0.1, volatility=0.3)], total=1000
    )
    assert allocs[0].weight == 0.0


@pytest.mark.criteria("FUN-4")
def test_kelly_scales_down_above_full_investment() -> None:
    estimates = [
        AssetEstimate("A", expected_return=0.5, volatility=0.3),
        AssetEstimate("B", expected_return=0.4, volatility=0.3),
    ]
    allocs = kelly_allocations(estimates, total=1000, kelly_multiplier=1.0)
    assert gross_exposure(allocs) == pytest.approx(1.0)
    assert sum(a.amount for a in allocs) == pytest.approx(1000.0)


def test_kelly_respects_max_weight() -> None:
    allocs = kelly_allocations(
        [AssetEstimate("A", expected_return=0.5, volatility=0.3)],
        total=1000,
        kelly_multiplier=1.0,
        max_weight=0.3,
    )
    assert allocs[0].weight == pytest.approx(0.3)


# --- compare / orchestration ----------------------------------------------


class FakeFundamentals:
    def __init__(self, mapping):
        self._mapping = mapping

    def financials(self, security):
        return self._mapping[security.symbol]


def test_annualized_volatility() -> None:
    vol = annualized_volatility(bars_from_closes([100, 110, 99]), periods_per_year=252)
    assert vol == pytest.approx(0.1 * (252**0.5))


def test_analyze_ranks_by_upside_and_builds_kelly() -> None:
    fundamentals = FakeFundamentals(
        {"CHEAP": make_financials("CHEAP"), "RICH": make_financials("RICH")}
    )
    market = InMemoryMarketData(
        {
            Security("CHEAP"): bars_from_closes(
                [10, 11, 10, 12]
            ),  # low price -> upside
            Security("RICH"): bars_from_closes([90, 95, 100, 110]),  # high price
        }
    )
    analyses = analyze(["CHEAP", "RICH"], fundamentals, market)
    assert [a.symbol for a in analyses] == ["CHEAP", "RICH"]  # sorted by upside desc
    assert analyses[0].upside > analyses[1].upside

    estimates = {e.symbol: e for e in kelly_estimates(analyses, market, lookback=10)}
    assert estimates["CHEAP"].expected_return == pytest.approx(analyses[0].upside)
    assert estimates["CHEAP"].volatility > 0
