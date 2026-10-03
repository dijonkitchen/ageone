from pathlib import Path

import pandas as pd
import pytest
import synthetic

from screener.standardize import standardize

FIXTURES = Path(__file__).parent / "fixtures"


def test_openbb_output_matches_recording(blk_facts):
    """Fails when an OpenBB upgrade changes standardized values; see fixtures/README.md."""
    got = standardize(blk_facts).line_items.reset_index(drop=True)
    want = pd.read_csv(FIXTURES / "BLK.standardized.csv", dtype={"period_ending": str})
    pd.testing.assert_frame_equal(got, want, check_dtype=False)


def test_real_filing_bvps_inputs(blk_facts):
    std = standardize(blk_facts)
    assert std.company_type and std.currency == "USD"
    # Gap fill reads year-end shares from the 10-K balance sheet tag.
    shares = std.line_items.query("tag == 'shares_outstanding'").set_index("fiscal_year")["value"]
    assert sorted(shares.index) == [2023, 2024, 2025] and (shares > 100e6).all()
    source = std.line_items.query("tag == 'shares_outstanding'")["source"].iloc[0]
    assert source == "gap-fill:us-gaap:CommonStockSharesOutstanding"
    assert set(std.filings["form"]) == {"10-K"}


def test_gap_fill_falls_back_to_cover_page_shares():
    facts, truth = synthetic.build()
    del facts["facts"]["us-gaap"]["CommonStockSharesOutstanding"]
    std = standardize(facts)
    shares = std.line_items.query("tag == 'shares_outstanding'")
    assert set(shares["source"]) == {"gap-fill:dei:EntityCommonStockSharesOutstanding"}
    assert shares.set_index("fiscal_year")["value"][2024] == pytest.approx(truth[2024]["shares"])


def test_split_ratio_facts_are_kept():
    std = standardize(synthetic.build()[0])
    assert std.split_facts["ratio"].tolist() == [4.0]


def test_latest_10k_wins_even_when_it_restates_years_later():
    facts, truth = synthetic.build()
    rows = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    first = next(r for r in rows if r["end"] == "2015-12-31" and r["fy"] == 2015)
    # A 10-K filed three years on restates 2015, past OpenBB's own 450-day window.
    rows.append({**first, "val": first["val"] * 1.05, "fy": 2018, "accn": synthetic.accession(2018), "filed": "2019-02-15"})

    def revenue(std):
        items = std.line_items.query("fiscal_year == 2015 and tag in ('revenue', 'total_revenue', 'operating_revenue')")
        return items["value"].iloc[0]

    assert revenue(standardize(facts)) == pytest.approx(truth[2015]["revenue"] * 1.05)
    assert revenue(standardize(facts, pit_mode=True)) == pytest.approx(truth[2015]["revenue"])
