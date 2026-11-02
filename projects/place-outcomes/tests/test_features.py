import csv

import duckdb
import pytest

from place_outcomes import features
from tests.conftest import DATA


def test_crosswalk_weights_sum_to_one(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("SELECT zip, sum(weight) FROM crosswalk GROUP BY zip").fetchall()
    assert rows
    assert all(abs(total - 1) < 1e-9 for _, total in rows)


def test_feature_matches_hand_computed_value(con: duckdb.DuckDBPyConnection) -> None:
    """Recompute one ZIP's school score from the raw files with plain Python."""
    zip_code = "94118"
    with (DATA / "zcta_tract_rel_10.txt").open() as f:
        rel = [r for r in csv.DictReader(f) if r["ZCTA5"] == zip_code]
    with (DATA / "atlas_covariates.csv").open() as f:
        cov = {
            f"{int(r['state']):02d}{int(r['county']):03d}{int(r['tract']):06d}": r["gsmn_math_g3_2013"]
            for r in csv.DictReader(f)
        }
    pairs = [(float(r["POPPT"]), float(cov[r["GEOID"]])) for r in rel if r["GEOID"] in cov and cov[r["GEOID"]]]
    expected = sum(w * x for w, x in pairs) / sum(w for w, _ in pairs)
    row = con.execute("SELECT school_math, n_tracts FROM zip_features WHERE zip = ?", [zip_code]).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(expected)
    assert row[1] == len([r for r in rel if float(r["POPPT"]) > 0])


def test_a_zip_is_served_by_the_county_holding_most_of_its_residents(con: duckdb.DuckDBPyConnection) -> None:
    assert con.execute("SELECT county_fips FROM zip_features WHERE zip = '94118'").fetchall() == [("06075",)]


def test_quality_checks_pass_on_real_samples(con: duckdb.DuckDBPyConnection) -> None:
    assert "crosswalk weights sum to 1" in features.check(con)


def test_quality_check_catches_broken_weights(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("UPDATE crosswalk SET weight = weight * 0.9 WHERE zip = '94118'").fetchall()
    with pytest.raises(features.DataQualityError, match="weights"):
        features.check(con)


def test_quality_check_catches_missing_factor(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("UPDATE zip_features SET school_math = NULL").fetchall()
    with pytest.raises(features.DataQualityError, match="school_math"):
        features.check(con)


def test_quality_check_catches_implausible_values(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("UPDATE zip_features SET poverty_share = 7 WHERE zip = '94118'").fetchall()
    con.execute("UPDATE zip_value SET value = 5 WHERE zip = '94118'").fetchall()
    with pytest.raises(features.DataQualityError) as error:
        features.check(con)
    assert "in [0, 1]" in str(error.value)
    assert "home values" in str(error.value)
