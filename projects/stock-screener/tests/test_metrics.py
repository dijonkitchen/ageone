import math

import pandas as pd
import pytest
import synthetic

from screener import metrics
from screener.standardize import standardize


@pytest.fixture(scope="module")
def company():
    facts, truth = synthetic.build()
    std = standardize(facts)
    result = metrics.compute(std.line_items, std.split_facts)
    series = result.values.pivot(index="fiscal_year", columns="metric", values="value")
    return std, result, series, truth


def test_ten_plus_years_of_every_per_share_series(company):
    _, _, series, _ = company
    for name in ("bvps", "tbvps", "eps", "revenue_ps", "ocf_ps", "fcf_ps", "dps"):
        assert series[name].notna().sum() >= 10, name


def test_per_share_values_are_split_adjusted(company):
    _, _, series, truth = company
    for year, t in truth.items():
        assert series.loc[year, "bvps"] == pytest.approx(t["equity"] / t["shares"], rel=1e-6)
        assert series.loc[year, "tbvps"] == pytest.approx((t["equity"] - t["goodwill"]) / t["shares"], rel=1e-6)
        # Reported EPS is rounded to cents on the old share basis.
        assert series.loc[year, "eps"] == pytest.approx(t["net"] / t["diluted_shares"], rel=0.03)
        fcf = (t["ocf"] - t["capex"]) / t["diluted_shares"]
        assert series.loc[year, "fcf_ps"] == pytest.approx(fcf, rel=1e-6)
        assert series.loc[year, "dps"] == pytest.approx(t["dividends"] / t["shares"], rel=0.01)


def test_ratios(company):
    _, _, series, truth = company
    t = truth[2024]
    assert series.loc[2024, "roe"] == pytest.approx(t["net"] / t["equity"], rel=1e-6)
    assert series.loc[2024, "roa"] == pytest.approx(t["net"] / t["assets"], rel=1e-6)
    assert series.loc[2024, "gross_margin"] == pytest.approx(0.5, rel=1e-6)
    assert series.loc[2024, "operating_margin"] == pytest.approx(0.25, rel=1e-6)
    assert series.loc[2024, "current_ratio"] == pytest.approx(0.4 / 0.25, rel=1e-6)
    assert series.loc[2024, "debt_to_equity"] == pytest.approx(0.3, rel=1e-6)
    assert series.loc[2024, "interest_coverage"] == pytest.approx(t["operating"] / t["interest"], rel=1e-6)
    roic = t["operating"] * (1 - 0.21) / (t["equity"] + t["debt"])
    assert series.loc[2024, "roic"] == pytest.approx(roic, rel=1e-4)


def test_splits_found_once_each(company):
    _, result, _, _ = company
    flow = [s for s in result.splits if s.series == "diluted_shares_reported"]
    assert [(s.ratio, s.source) for s in flow] == [(2.0, "detected"), (4.0, "tagged")]


def test_restatement_latest_wins_and_point_in_time_keeps_first(company):
    std, _, _, truth = company
    revenue = lambda s: s.line_items.query("tag == 'total_revenue' and fiscal_year == @synthetic.RESTATED_YEAR")["value"].iloc[0]
    first = truth[synthetic.RESTATED_YEAR]["revenue"]
    assert revenue(std) == pytest.approx(first * synthetic.RESTATEMENT, rel=1e-6)
    assert revenue(standardize(synthetic.build()[0], pit_mode=True)) == pytest.approx(first, rel=1e-6)


def test_every_year_traces_to_a_filing(company):
    std, _, _, _ = company
    assert set(std.filings["fiscal_year"]) == set(synthetic.YEARS)
    assert std.filings["accession"].notna().all()


def test_negative_equity_gives_no_roe_and_records_gaps():
    facts, _ = synthetic.build(start_equity=-50e6, growth=-0.5)
    std = standardize(facts)
    result = metrics.compute(std.line_items, std.split_facts)
    assert not (result.values["metric"] == "roe").any()
    gaps = result.gaps.set_index("metric")
    assert gaps.loc["roe", "years"] == 0


def test_gap_report_names_missing_line_items():
    facts, _ = synthetic.build()
    del facts["facts"]["us-gaap"]["AssetsCurrent"]
    del facts["facts"]["us-gaap"]["LiabilitiesCurrent"]
    std = standardize(facts)
    gaps = metrics.compute(std.line_items, std.split_facts).gaps.set_index("metric")
    assert gaps.loc["current_ratio", "years"] == 0
    assert "total_current_assets" in gaps.loc["current_ratio", "missing"]
    assert gaps.loc["bvps", "missing"] == ""


def test_definitions_name_their_concepts():
    eps = metrics.definitions().metrics["eps"]
    assert eps.concepts == ("diluted_eps",)
    assert "weighted_ave_diluted_shares_os" in metrics.definitions().metrics["fcf_ps"].concepts


# Growth and consistency


@pytest.mark.parametrize("start,end", [(0, 10), (-1, 10), (10, 0), (10, -5)])
def test_cagr_undefined_at_or_below_zero(start, end):
    assert math.isnan(metrics.cagr(start, end, 10))


def test_cagr():
    assert metrics.cagr(100, 200, 1) == pytest.approx(1.0)
    assert metrics.cagr(100, 100 * 1.1**10, 10) == pytest.approx(0.10)


def test_steady_compounder_stats():
    series = pd.Series([100 * 1.1**i for i in range(11)], index=range(2014, 2025))
    stats = metrics.series_stats(series, growth=True)
    assert stats["cagr"] == pytest.approx(0.10)
    assert stats["years_grew"] == 10
    assert stats["growth_streak"] == 10
    assert stats["growth_std"] == pytest.approx(0, abs=1e-12)
    assert stats["r2"] == pytest.approx(1.0)
    assert stats["cagr_undefined"] == 0


def test_lucky_endpoints_score_low_consistency():
    series = pd.Series([100, 60, 150, 50, 140, 70, 200], index=range(2018, 2025))
    stats = metrics.series_stats(series, growth=True)
    assert stats["cagr"] == pytest.approx(2 ** (1 / 6) - 1)
    assert stats["years_grew"] == 3
    assert stats["growth_streak"] == 1
    assert stats["r2"] < 0.5
    assert stats["growth_std"] > 0.5


def test_missing_years_are_not_interpolated():
    series = pd.Series([100.0, 110.0, None, 133.1], index=[2021, 2022, 2023, 2024])
    stats = metrics.series_stats(series, growth=True)
    assert stats["years"] == 3
    assert stats["years_grew"] == 1  # only 2021 -> 2022 is a consecutive pair
    assert stats["cagr"] == pytest.approx(0.10)  # over the 3 years between 2021 and 2024


def test_negative_start_has_no_cagr_or_r2():
    stats = metrics.series_stats(pd.Series([-5.0, 2.0, 4.0], index=[2022, 2023, 2024]), growth=True)
    assert math.isnan(stats["cagr"]) and stats["cagr_undefined"] == 1 and math.isnan(stats["r2"])


def test_windows_end_at_latest_year():
    values = pd.DataFrame({"fiscal_year": range(2005, 2025), "metric": "bvps",
                           "value": [1.1**i for i in range(20)]})
    stats = metrics.window_stats(values).set_index(["window", "stat"])["value"]
    assert stats[("5", "years")] == 6
    assert stats[("10", "years")] == 11
    assert stats[("all", "years")] == 20
    assert stats[("10", "cagr")] == pytest.approx(0.10)
