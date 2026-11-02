import duckdb
import pandas as pd

from place_outcomes import models


def test_spatial_folds_never_split_a_county(con: duckdb.DuckDBPyConnection) -> None:
    df = models.frame(con)
    folds = models.spatial_folds(df["county_fips"])
    assert len(folds) > 1
    for train, test in folds:
        assert not set(df["county_fips"].iloc[train]) & set(df["county_fips"].iloc[test])
    assert sorted(i for _, test in folds for i in test) == list(range(len(df)))


def test_outcomes_report_every_score(con: duckdb.DuckDBPyConnection) -> None:
    result = models.outcomes(models.frame(con))
    assert set(result) == {"adult_income_rank", "incarceration_rate"}
    assert set(result["adult_income_rank"]["r2"]) == {"baseline", "linear", "boosted"}


def test_price_reports_school_price_per_state_and_residuals(con: duckdb.DuckDBPyConnection) -> None:
    result = models.price(models.frame(con), extremes=3)
    assert set(result["school_price_per_sd"]) == {"CA", "NJ"}
    above: pd.DataFrame = result["above_prediction"]
    assert len(above) == 3
    assert above["residual"].is_monotonic_decreasing
    assert (result["below_prediction"]["residual"] < 0).all()
