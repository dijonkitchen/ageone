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
