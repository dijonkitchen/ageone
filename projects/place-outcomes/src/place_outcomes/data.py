"""Download source files with a manifest, and load Zillow's home values into DuckDB."""

import hashlib
import io
import json
import ssl
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import certifi
import duckdb
import pandas as pd

from place_outcomes.config import (
    CENSUS_OPPORTUNITY,
    GRF_MEMBER,
    GRF_URL,
    LEA_ZCTA_FILE,
    SEDA_FILE,
    SEDA_URL,
    STATE_FIPS,
    STATES,
    TRACT_COVARIATES_FILE,
    TRACT_OUTCOMES_FILE,
    ZCTA_TRACT_FILE,
    ZCTA_TRACT_URL,
    ZHVI_FILE,
    ZHVI_URL,
    Paths,
)

USER_AGENT = "ageone-place-outcomes (https://github.com/dijonkitchen/ageone)"


def fetch(paths: Paths, url: str = ZHVI_URL, name: str = ZHVI_FILE) -> Path:
    """Download `url` to raw/`name`, and record its URL, time, size, and SHA-256 in the manifest.

    Zillow rewrites the file around the 16th of each month, so it is downloaded again every time.
    """
    paths.raw.mkdir(parents=True, exist_ok=True)
    out = paths.raw / name
    tmp = out.with_suffix(".part")
    digest = hashlib.sha256()
    with _open(url) as response, tmp.open("wb") as f:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            f.write(chunk)
    tmp.replace(out)  # Never leave a half-written file where `load` would read it.
    record(paths, name, url, digest.hexdigest())
    return out


def _open(url: str) -> io.BufferedIOBase:
    """Open `url` with the system's trusted roots, falling back to Mozilla's (certifi) when the
    server's chain ends at a root the system store lacks, as stacks.stanford.edu's emSign chain can."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(request, timeout=600)  # type: ignore[no-any-return]
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        context = ssl.create_default_context(cafile=certifi.where())
        return urllib.request.urlopen(request, timeout=600, context=context)  # type: ignore[no-any-return]


def fetch_factors(paths: Paths, seda: bool = False) -> None:
    """Download the area factor and outcome files. SEDA only with `seda`, since downloading it means
    accepting its data use agreement."""
    for name in (TRACT_OUTCOMES_FILE, TRACT_COVARIATES_FILE):
        fetch(paths, CENSUS_OPPORTUNITY + name, name)
    fetch(paths, ZCTA_TRACT_URL, ZCTA_TRACT_FILE)
    grf = fetch(paths, GRF_URL, "GRF24.zip")
    with zipfile.ZipFile(grf) as z:
        frame = pd.read_sas(io.BytesIO(z.read(GRF_MEMBER)), format="sas7bdat", encoding="latin1")
    frame = frame[frame["LEAID"].str[:2].isin(STATE_FIPS.values())]
    frame[["LEAID", "ZCTA5CE20", "LANDAREA"]].to_csv(paths.raw / LEA_ZCTA_FILE, index=False)
    grf.unlink()  # The national file is 59 MB; only the two states' rows are kept.
    if seda:
        fetch(paths, SEDA_URL, SEDA_FILE)


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
