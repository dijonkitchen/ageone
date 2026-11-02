import json
from pathlib import Path

import duckdb

from place_outcomes import data, report


def test_report_has_caveats_and_every_question(con: duckdb.DuckDBPyConnection) -> None:
    page = report.build(con)
    for heading in ("1. Outcomes", "2. Price", "3. Forecast", "Caveats", "not shown to cause"):
        assert heading in page
    assert "cross-validated R²" in page


def test_report_marks_highlight_zips_from_an_uncommitted_file(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    config = tmp_path / "places.local.json"
    zips = [row[0] for row in con.execute("SELECT zip FROM zip_features").fetchall()]
    config.write_text(json.dumps({"highlight_zips": zips}))
    assert "★" in report.build(con, config)
    assert "★" not in report.build(con)


def test_digest_is_a_sha256(tmp_path: Path) -> None:
    f = tmp_path / "x"
    f.write_bytes(b"abc")
    assert data.digest(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
