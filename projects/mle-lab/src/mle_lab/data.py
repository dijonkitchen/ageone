"""Fetch daily series from FRED as CSV, and load them into DuckDB."""

import urllib.request
from pathlib import Path

import duckdb

from mle_lab.config import FRED_CSV, SERIES, Paths


def fetch(paths: Paths) -> None:
    """Download each series' full history to data/raw/<id>.csv (no API key needed)."""
    paths.raw.mkdir(parents=True, exist_ok=True)
    for series_id in SERIES.values():
        out = paths.raw / f"{series_id}.csv"
        tmp = out.with_suffix(".part")
        with urllib.request.urlopen(FRED_CSV.format(series_id), timeout=60) as response:
            tmp.write_bytes(response.read())
        tmp.replace(out)  # Never leave a half-written file where `load` would read it.


def load(con: duckdb.DuckDBPyConnection, raw: Path) -> int:
    """Rebuild the `prices` table from the CSVs: one row per day both series have a value."""
    selects = [
        f"SELECT observation_date::DATE AS date, TRY_CAST({sid} AS DOUBLE) AS {name} "
        f"FROM read_csv('{raw / f'{sid}.csv'}', all_varchar = true)"
        for name, sid in SERIES.items()
    ]
    # FRED marks holidays and gaps as empty or "."; TRY_CAST makes those NULL, and the join drops them.
    names = list(SERIES)
    joined = f"({selects[0]}) a JOIN ({selects[1]}) b USING (date)"
    con.execute(
        f"CREATE OR REPLACE TABLE prices AS SELECT date, {', '.join(names)} FROM {joined} "
        f"WHERE {' AND '.join(f'{n} IS NOT NULL' for n in names)} ORDER BY date"
    )
    row = con.execute("SELECT count(*) FROM prices").fetchone()
    assert row is not None
    return int(row[0])
