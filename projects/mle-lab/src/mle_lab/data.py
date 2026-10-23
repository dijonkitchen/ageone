"""Download EIA-930 balance files, and load one region's hourly demand into DuckDB."""

import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import duckdb

from mle_lab.config import EIA_URL, FIRST_YEAR, REGION, Paths

USER_AGENT = "ageone-mle-lab (https://github.com/dijonkitchen/ageone)"


def fetch(paths: Paths, first_year: int = FIRST_YEAR, today: date | None = None) -> list[Path]:
    """Download each half-year file from `first_year` on. Past halves never change, so they are
    downloaded once; the current half is downloaded again every time, since EIA updates it daily."""
    today = today or date.today()
    paths.raw.mkdir(parents=True, exist_ok=True)
    fetched = []
    for year in range(first_year, today.year + 1):
        for half, starts in (("Jan_Jun", 1), ("Jul_Dec", 7)):
            if (year, starts) > (today.year, today.month):
                continue
            current = (year, starts) == (today.year, 1 if today.month < 7 else 7)
            out = paths.raw / f"EIA930_BALANCE_{year}_{half}.csv"
            if out.exists() and not current:
                continue
            request = urllib.request.Request(EIA_URL.format(year=year, half=half), headers={"User-Agent": USER_AGENT})
            tmp = out.with_suffix(".part")
            with urllib.request.urlopen(request, timeout=300) as response:
                tmp.write_bytes(response.read())
            tmp.replace(out)  # Never leave a half-written file where `load` would read it.
            fetched.append(out)
    return fetched


def load(con: duckdb.DuckDBPyConnection, raw: Path, region: str = REGION) -> int:
    """Rebuild the `demand` table for `region`: one row per hour, keyed by its UTC end."""
    con.execute(
        """
        CREATE OR REPLACE TABLE demand AS
        SELECT DISTINCT ON (utc_end)
            strptime("UTC Time at End of Hour", '%m/%d/%Y %I:%M:%S %p') AS utc_end,
            -- EIA's adjusted demand fills reporting gaps; numbers may carry thousands separators.
            TRY_CAST(replace("Demand (MW) (Adjusted)", ',', '') AS DOUBLE) AS demand,
            TRY_CAST(replace("Demand Forecast (MW)", ',', '') AS DOUBLE) AS operator_forecast
        FROM read_csv($glob, all_varchar = true, union_by_name = true)
        WHERE "Balancing Authority" = $region
        ORDER BY utc_end
        """,
        {"glob": str(raw / "EIA930_BALANCE_*.csv*"), "region": region},
    )
    row = con.execute("SELECT count(*) FROM demand").fetchone()
    assert row is not None
    return int(row[0])
