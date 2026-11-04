from datetime import date

import pytest

from roi.analysis import build_history, cagr, median_growth, yoy_growth
from roi.analysis.history import PerShare
from roi.domain import Financials


def fin(
    year: int, *, revenue: float, net_income: float, shares: float = 10.0
) -> Financials:
    return Financials(
        symbol="X",
        period_end=date(year, 12, 31),
        revenue=revenue,
        net_income=net_income,
        operating_cash_flow=net_income * 1.5,
        capital_expenditures=net_income * 0.5,
        total_debt=0.0,
        cash_and_equivalents=0.0,
        shareholders_equity=revenue * 0.5,
        shares_outstanding=shares,
    )


def test_per_share_from_financials() -> None:
    ps = PerShare.from_financials(fin(2023, revenue=1000, net_income=100, shares=10))
    assert ps.revenue == 100.0
    assert ps.earnings == 10.0  # EPS


@pytest.mark.criteria("FUN-6")
def test_yoy_growth_and_median() -> None:
    growth = yoy_growth([100.0, 110.0, 121.0])
    assert growth == [None, pytest.approx(0.1), pytest.approx(0.1)]
    assert median_growth(growth) == pytest.approx(0.1)


@pytest.mark.criteria("FUN-6")
def test_growth_none_when_prior_non_positive() -> None:
    # loss -> profit cannot be a sensible percentage
    growth = yoy_growth([-5.0, 10.0, 12.0])
    assert growth[1] is None
    assert growth[2] == pytest.approx(0.2)
    assert median_growth(growth) == pytest.approx(0.2)


def test_cagr() -> None:
    periods = [date(2021, 12, 31), date(2023, 12, 31)]  # ~2 years
    assert cagr([100.0, 121.0], periods) == pytest.approx(0.1, rel=1e-3)
    assert cagr([-1.0, 10.0], periods) is None  # non-positive base


@pytest.mark.criteria("FUN-6")
def test_build_history_computes_per_share_and_growth() -> None:
    series = [
        fin(2021, revenue=1000, net_income=100),
        fin(2022, revenue=1100, net_income=110),
        fin(2023, revenue=1210, net_income=121),
    ]
    hist = build_history(series)
    assert hist.symbol == "X"
    assert hist.periods == (date(2021, 12, 31), date(2022, 12, 31), date(2023, 12, 31))

    revenue = hist.summaries["revenue"]
    assert revenue.per_share == (100.0, 110.0, 121.0)
    assert revenue.median_growth == pytest.approx(0.1)
    assert revenue.cagr == pytest.approx(0.1, rel=1e-3)

    eps = hist.summaries["earnings"]
    assert eps.per_share == (10.0, 11.0, 12.1)
    assert eps.median_growth == pytest.approx(0.1)


def test_build_history_keeps_only_last_n_years() -> None:
    series = [fin(2010 + i, revenue=1000 * (1 + i), net_income=100) for i in range(12)]
    hist = build_history(series, years=10)
    assert len(hist.rows) == 10
    assert hist.periods[0] == date(2012, 12, 31)  # oldest two dropped


def test_build_history_requires_data() -> None:
    with pytest.raises(ValueError):
        build_history([])
