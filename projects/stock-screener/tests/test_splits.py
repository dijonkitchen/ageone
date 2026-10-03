import pandas as pd

from screener import splits


def test_detects_whole_number_split_and_adjusts_before_it():
    shares = pd.Series([100.0, 98, 196, 194], index=[2020, 2021, 2022, 2023])
    found = splits.detect(shares, [], "s")
    assert found == [splits.Split(2022, 2.0, "detected", "s")]
    assert splits.factors(shares.index, found).tolist() == [2.0, 2.0, 1.0, 1.0]


def test_reverse_split():
    shares = pd.Series([1000.0, 100], index=[2022, 2023])
    assert splits.detect(shares, [], "s")[0].ratio == 0.1


def test_tagged_ratio_matches_non_whole_jump():
    shares = pd.Series([100.0, 150], index=[2022, 2023])
    assert splits.detect(shares, [], "s") == []
    assert splits.detect(shares, [1.5], "s") == [splits.Split(2023, 1.5, "tagged", "s")]


def test_fully_restated_split_is_not_adjusted_twice():
    # The filer restated every year onto the new basis: no jump, nothing to adjust.
    shares = pd.Series([200.0, 198, 196], index=[2021, 2022, 2023])
    assert splits.detect(shares, [2.0], "s") == []


def test_share_issuance_is_not_a_split_when_eps_does_not_drop():
    shares = pd.Series([100.0, 200], index=[2022, 2023])
    eps = pd.Series([2.0, 2.1], index=[2022, 2023])
    assert splits.detect(shares, [], "s", eps) == []
    eps_split = pd.Series([2.0, 1.05], index=[2022, 2023])
    assert len(splits.detect(shares, [], "s", eps_split)) == 1


def test_small_changes_are_not_splits():
    shares = pd.Series([100.0, 120, 90, 130], index=[2020, 2021, 2022, 2023])
    assert splits.detect(shares, [], "s") == []
