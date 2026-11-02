"""Download source files with a manifest, and load Zillow's home values into DuckDB."""

import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from place_outcomes.config import STATES, ZHVI_FILE, ZHVI_URL, Paths

USER_AGENT = "ageone-place-outcomes (https://github.com/dijonkitchen/ageone)"


def fetch(paths: Paths, url: str = ZHVI_URL, name: str = ZHVI_FILE) -> Path:
    """Download `url` to raw/`name`, and record its URL, time, size, and SHA-256 in the manifest.

    Zillow rewrites the file around the 16th of each month, so it is downloaded again every time.
    """
    paths.raw.mkdir(parents=True, exist_ok=True)
    out = paths.raw / name
    tmp = out.with_suffix(".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=600) as response, tmp.open("wb") as f:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            f.write(chunk)
    tmp.replace(out)  # Never leave a half-written file where `load` would read it.
    record(paths, name, url, digest.hexdigest())
    return out


def record(paths: Paths, name: str, url: str, sha256: str) -> None:
    manifest = json.loads(paths.manifest.read_text()) if paths.manifest.exists() else {}
    manifest[name] = {
        "url": url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "bytes": (paths.raw / name).stat().st_size,
        "sha256": sha256,
    }
    paths.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def load(con: duckdb.DuckDBPyConnection, raw: Path, states: tuple[str, ...] = STATES) -> int:
    """Rebuild `zhvi`: one row per ZIP and month (first of the month) with a value, for `states`.

    The file is wide, one column per month-end date, so it is unpivoted to long form.
    """
    files = sorted(raw.glob(f"{Path(ZHVI_FILE).stem}*.csv*"))
    if not files:
        raise SystemExit(f"no Zillow file in {raw}: run `places fetch`")
    con.execute(
        """
        CREATE OR REPLACE TABLE zhvi AS
        SELECT lpad(RegionName, 5, '0') AS zip, State AS state, CountyName AS county, Metro AS metro,
               date_trunc('month', strptime(month, '%Y-%m-%d'))::DATE AS month,
               TRY_CAST(value AS DOUBLE) AS value
        FROM (
            UNPIVOT (
                SELECT * EXCLUDE (RegionID, SizeRank, RegionType, StateName, City)
                FROM read_csv($file, all_varchar = true)
                WHERE list_contains($states, State)
            )
            ON COLUMNS(* EXCLUDE (RegionName, State, CountyName, Metro)) INTO NAME month VALUE value
        )
        WHERE TRY_CAST(value AS DOUBLE) > 0
        ORDER BY zip, month
        """,
        {"file": str(files[-1]), "states": list(states)},
    )
    row = con.execute("SELECT count(*) FROM zhvi").fetchone()
    assert row is not None
    return int(row[0])
