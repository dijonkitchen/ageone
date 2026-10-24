import io
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from mle_lab import data, features
from mle_lab.config import Paths


def test_fetch_downloads_past_halves_once_and_the_current_one_every_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls: list[str] = []

    def fake_urlopen(request: object, timeout: int) -> io.BytesIO:
        urls.append(request.full_url)  # type: ignore[attr-defined]
        return io.BytesIO(b"Balancing Authority\nERCO\n")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    paths = Paths(tmp_path)
    data.fetch(paths, first_year=2024, today=date(2025, 8, 1))
    assert sorted(p.name for p in paths.raw.iterdir()) == [
        "EIA930_BALANCE_2024_Jan_Jun.csv",
        "EIA930_BALANCE_2024_Jul_Dec.csv",
        "EIA930_BALANCE_2025_Jan_Jun.csv",
        "EIA930_BALANCE_2025_Jul_Dec.csv",
    ]
    assert all(u.startswith("https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/") for u in urls)
    urls.clear()
    data.fetch(paths, first_year=2024, today=date(2025, 8, 2))
    assert [u.rsplit("/", 1)[1] for u in urls] == ["EIA930_BALANCE_2025_Jul_Dec.csv"]


def test_load_keeps_one_region_one_row_per_hour(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        demand = con.execute("SELECT * FROM demand").df()
    assert len(demand) == 11664
    assert demand["utc_end"].is_unique
    assert demand["demand"].between(30_000, 90_000).all()


def row(con: duckdb.DuckDBPyConnection, utc_end: str) -> pd.Series:
    return con.execute("SELECT * FROM features WHERE utc_end = $t::TIMESTAMP", {"t": utc_end}).df().iloc[0]


def demand_at(con: duckdb.DuckDBPyConnection, utc_end: str) -> float:
    found = con.execute("SELECT demand FROM demand WHERE utc_end = $t::TIMESTAMP", {"t": utc_end}).fetchone()
    assert found is not None
    return float(found[0])


def test_features_follow_local_time_and_use_lagged_demand(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        # The hour ending 18:00 UTC on Thursday 2024-07-04 is 12:00-13:00 in Texas (UTC-5 in summer).
        r = row(con, "2024-07-04 18:00")
        assert (r.date.date(), r.hour, r.dow, r.holiday) == (date(2024, 7, 4), 12, 4, 1)
        assert r.lag_2d == demand_at(con, "2024-07-02 18:00")
        assert r.lag_7d == r.naive_forecast == demand_at(con, "2024-06-27 18:00")
        # D-2 is 2024-07-02 local: hours ending 06:00 UTC on the 2nd through 05:00 UTC on the 3rd.
        day = con.execute(
            "SELECT avg(demand), min(demand), max(demand) FROM demand "
            "WHERE utc_end BETWEEN '2024-07-02 06:00' AND '2024-07-03 05:00'"
        ).fetchone()
        assert day is not None
        assert (r.prev_mean, r.prev_min, r.prev_max) == pytest.approx(day)
        # Winter is UTC-6; the spring-forward day has 23 hours.
        assert row(con, "2025-01-15 18:00").hour == 11
        assert con.execute("SELECT count(*) FROM features WHERE date = '2024-03-10'").fetchone() == (23,)


def test_features_never_see_past_the_cutoff(lab: Paths) -> None:
    """Changing demand from the morning of D-1 on changes none of D's features, only its label."""
    with duckdb.connect(str(lab.warehouse)) as con:
        query = "SELECT * FROM features WHERE date = '2024-08-15' ORDER BY utc_end"
        before = con.execute(query).df()
        # 2024-08-14 starts at 05:00 UTC in Texas; scramble everything from then on.
        con.execute("UPDATE demand SET demand = demand * 1.5 + 1000 WHERE utc_end > '2024-08-14 05:00'")
        features.build(con)
        after = con.execute(query).df()
    assert len(before) == 24
    labels = ["demand", "operator_forecast"]
    pd.testing.assert_frame_equal(before.drop(columns=labels), after.drop(columns=labels))
    assert (after["demand"] > before["demand"]).all()


def test_quality_checks_pass_on_real_data_and_catch_bad_data(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse)) as con:
        assert features.check(con) == []
        con.execute("UPDATE demand SET demand = 999999 WHERE utc_end = '2024-07-04 18:00'")
        con.execute("DELETE FROM demand WHERE utc_end BETWEEN '2024-09-01' AND '2024-09-02'")
        assert features.check(con) == [
            "implausible demand (under a third or over triple the median)",
            "missing hours in the data",
        ]
        con.execute("DELETE FROM demand WHERE utc_end < '2024-06-01'")
        assert "under a year of hours" in features.check(con)


def test_labeled_holds_only_days_known_by_the_morning(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        known = features.labeled(con, date(2024, 9, 1))
        tomorrow = features.day(con, date(2024, 9, 2))
    assert known["date"].max() == pd.Timestamp("2024-08-31")
    assert len(tomorrow) == 24
