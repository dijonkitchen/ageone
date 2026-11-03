import math

import duckdb
import pandas as pd

from place_outcomes import analysis, factors
from place_outcomes.config import Paths


def test_every_zillow_zip_gets_a_row_with_tract_and_school_values(places: Paths) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        df = con.execute("SELECT * FROM zip_factors").df()
        assert factors.check(con) == []
    assert len(df) == 40 and df["zip"].is_unique
    assert df["kfr"].between(0, 1).all() and df["achievement"].notna().all()
    assert (df["value_month"] == pd.Timestamp(2026, 9, 1)).all()


def test_tract_values_are_population_weighted_into_zips(places: Paths) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        zip_code, got = con.execute("SELECT zip, kfr FROM zip_factors ORDER BY zip LIMIT 1").fetchone() or ("", 0.0)
        parts = con.execute(
            "SELECT t.pop, x.kfr FROM zcta_tract t JOIN tracts x USING (tract) "
            "WHERE t.zip = $z AND t.pop > 0 AND x.kfr IS NOT NULL",
            {"z": zip_code},
        ).fetchall()
    assert len(parts) > 1
    assert math.isclose(got, sum(p * k for p, k in parts) / sum(p for p, _ in parts))


def test_school_values_are_land_weighted_over_districts_with_scores(places: Paths) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        zip_code, got, n = con.execute(
            "SELECT zip, achievement, districts FROM zip_factors ORDER BY districts DESC, zip LIMIT 1"
        ).fetchone() or ("", 0.0, 0)
        parts = con.execute(
            "SELECT l.land, s.achievement FROM lea_zcta l JOIN seda s USING (leaid) WHERE l.zip = $z AND l.land > 0",
            {"z": zip_code},
        ).fetchall()
    assert n == len(parts) > 1
    assert math.isclose(got, sum(a * v for a, v in parts) / sum(a for a, _ in parts))


def test_missing_seda_leaves_school_values_empty_and_check_flags_it(lab: Paths) -> None:
    import shutil

    from conftest import DATA, FACTOR_FILES

    for name in FACTOR_FILES[:-1]:
        shutil.copy(DATA / name, lab.raw / name)
    with duckdb.connect(str(lab.warehouse)) as con:
        factors.load(con, lab.raw)
        factors.build(con)
        assert con.execute("SELECT count(achievement) FROM zip_factors").fetchone() == (0,)
        assert any("achievement" in p for p in factors.check(con))
        assert analysis.frame(con).empty


def test_folds_never_split_a_county(places: Paths) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        df = analysis.frame(con)
    seen = set()
    for train, test in analysis.folds(df):
        test_counties = set(df.loc[test, "county"])
        assert not test_counties & set(df.loc[train, "county"])
        seen |= set(test)
    assert seen == set(range(len(df)))


def test_outcomes_and_price_report_scores_premiums_and_residuals(places: Paths) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        df = analysis.frame(con)
    q1 = analysis.outcomes(df)
    q2 = analysis.price(df)
    assert q1.target == "kfr" and q2.scores.target == "log_value"
    assert set(q1.adds) == {*analysis.FACTORS, *analysis.BASELINE}
    assert set(q2.school_premium) == {"CA", "NJ"}
    assert len(q2.residuals) == len(df) and q2.residuals["gap"].is_monotonic_increasing
    for s in (q1, q2.scores):
        assert all(math.isfinite(v) for v in (s.baseline_r2, s.linear_r2, s.boosted_r2))
