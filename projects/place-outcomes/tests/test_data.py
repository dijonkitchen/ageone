import math
from datetime import date

import duckdb
import pandas as pd

from place_outcomes import features
from place_outcomes.config import Paths


def test_load_unpivots_zillow_to_zip_months(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        states = dict(con.execute("SELECT state, count(DISTINCT zip) FROM zhvi GROUP BY state").fetchall())
        first, last = con.execute("SELECT min(month), max(month) FROM zhvi").fetchone() or (None, None)
        zips = [z for (z,) in con.execute("SELECT DISTINCT zip FROM zhvi").fetchall()]
    assert states == {"CA": 20, "NJ": 20}
    assert first == date(2000, 1, 1) and last == date(2026, 9, 1)
    assert all(len(z) == 5 for z in zips)  # New Jersey ZIPs keep their leading zero.


def test_features_match_hand_computed_values(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        zip_code = con.execute("SELECT zip FROM zhvi WHERE state = 'NJ' ORDER BY zip LIMIT 1").fetchone()
        assert zip_code is not None
        values = (
            con.execute("SELECT month, value FROM zhvi WHERE zip = $z ORDER BY month", {"z": zip_code[0]})
            .df()
            .set_index("month")["value"]
        )
        row = (
            con.execute("SELECT * FROM features WHERE zip = $z AND month = DATE '2020-06-01'", {"z": zip_code[0]})
            .df()
            .iloc[0]
        )

    def v(y: int, m: int) -> float:
        return float(values[pd.Timestamp(y, m, 1)])

    assert math.isclose(row["r1"], math.log(v(2020, 6) / v(2020, 5)))
    assert math.isclose(row["r12"], math.log(v(2020, 6) / v(2019, 6)))
    assert math.isclose(row["r60"], math.log(v(2020, 6) / v(2015, 6)))
    assert math.isclose(row["y"], math.log(v(2021, 6) / v(2020, 6)))
    assert row["label_month"] == pd.Timestamp(2021, 6, 1)


def test_features_never_use_values_after_their_month(lab: Paths) -> None:
    """Rebuilding on data cut at a month gives the same features for that month."""
    cut = date(2018, 3, 1)
    with duckdb.connect(str(lab.warehouse)) as con:
        full = features.origins(con, cut, cut).set_index("zip")
        con.execute("DELETE FROM zhvi WHERE month > $cut", {"cut": cut})
        features.build(con)
        truncated = features.origins(con, cut, cut).set_index("zip")
    cols = [c for c in full.columns if c not in ("y",)]
    pd.testing.assert_frame_equal(full[cols], truncated.loc[full.index, cols], check_dtype=False)
    assert truncated["y"].isna().all()  # Its label isn't published yet.


def test_labeled_only_returns_labels_published_by_as_of(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        rows = features.labeled(con, date(2015, 1, 1), date(2020, 12, 1), as_of=date(2019, 6, 1))
    assert rows["label_month"].max() <= pd.Timestamp(2019, 6, 1)
    assert rows["month"].max() == pd.Timestamp(2018, 6, 1)


def test_quality_checks_pass_on_real_data_and_catch_bad_values(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse)) as con:
        assert features.check(con) == []
        con.execute("UPDATE zhvi SET value = 5 WHERE zip = (SELECT min(zip) FROM zhvi) AND month = DATE '2010-01-01'")
        con.execute("INSERT INTO zhvi SELECT * FROM zhvi LIMIT 1")
        problems = features.check(con)
    assert any("implausible" in p for p in problems)
    assert any("duplicate" in p for p in problems)
