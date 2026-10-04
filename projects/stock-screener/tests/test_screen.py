import pytest

from screener.screen import Filter, Screen, Weight

SCREEN = """
name = "Compounders"
window = "10"
min_years = 10
exchanges = ["NYSE", "Nasdaq"]
columns = ["bvps.cagr", "roe.avg"]

[sort]
by = "score"
descending = true

[[filters]]
column = "bvps.cagr"
op = ">="
value = 0.0

[[score]]
column = "bvps.cagr"
weight = 2.0

[[score]]
column = "roe.avg"
weight = 1.0
"""


def test_file_round_trip():
    screen = Screen.loads(SCREEN)
    assert Screen.loads(screen.dumps()) == screen
    assert screen.score[1].higher_is_better is None


def test_screen_filters_sorts_and_ranks(con):
    results = Screen.loads(SCREEN).run(con)
    # BLK has 3 years; DEBT has negative book value, so no CAGR, and fails the filter.
    assert results["ticker"].tolist() == ["FAST", "SLOW"]
    # FAST ranks first on BVPS growth (weight 2), SLOW on average ROE (weight 1).
    assert results["score"].tolist() == pytest.approx([200 / 3, 100 / 3])
    # Equity grows 15% a year and buybacks shrink the share count 1% a year.
    assert results["bvps.cagr"].iloc[0] == pytest.approx(1.15 * 1.01 - 1)


def test_lower_is_better_direction(con):
    screen = Screen(window="all", score=[Weight("debt_to_equity.latest")], sort_by="score")
    results = screen.run(con).set_index("ticker")
    # Synthetic companies all carry 0.3 debt to equity; BlackRock's is lower, so it ranks first.
    assert results["score"].idxmax() == "BLK"


def test_missing_values_do_not_count_as_bad_ranks(con):
    screen = Screen(window="all", score=[Weight("bvps.cagr"), Weight("roe.avg")])
    results = screen.run(con).set_index("ticker")
    # DEBT has neither (negative equity): no score rather than the worst score.
    assert results.loc["DEBT", "score_coverage"] == 0.0
    assert results["score"].isna().tolist() == [t == "DEBT" for t in results.index]
    assert results["score"].dropna().between(0, 100).all()


def test_exchange_sic_and_recency_filters(con):
    assert Screen(window="all", exchanges=["Nasdaq"]).run(con)["ticker"].tolist() == ["SLOW"]
    assert Screen(window="all", sic_prefixes=["62"]).run(con)["ticker"].tolist() == ["BLK"]
    # Synthetic companies end in 2024 and BlackRock in 2025: an age of 0 keeps only BlackRock.
    assert Screen(window="all", max_fiscal_year_age=0).run(con)["ticker"].tolist() == ["BLK"]


def test_deterministic(con):
    screen = Screen.loads(SCREEN)
    assert screen.run(con).equals(screen.run(con))


@pytest.mark.parametrize("bad", [
    Screen(filters=[Filter("bvps.cagr; drop table companies", ">=", 0)]),
    Screen(filters=[Filter("bvps.cagr", "like", 0)]),
    Screen(score=[Weight("ticker")]),
    Screen(window="7"),
    Screen(sort_by="nope"),
])
def test_rejects_unknown_columns_and_operators(bad):
    with pytest.raises(ValueError):
        bad.validate()
