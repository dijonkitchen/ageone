from datetime import date
from pathlib import Path

import duckdb

from place_outcomes import analysis, report
from place_outcomes.config import Paths


def test_report_writes_every_section_and_highlights_local_places(places: Paths, tmp_path: Path) -> None:
    with duckdb.connect(str(places.warehouse), read_only=True) as con:
        df = analysis.frame(con)
    mine = tmp_path / "places.local.toml"
    mine.write_text(f'zips = ["{df["zip"].iloc[0]}"]\n')
    out = report.write(
        places.data_dir / "report.html",
        analysis.outcomes(df),
        analysis.price(df),
        report.highlights(mine),
        date(2026, 9, 1),
    )
    page = out.read_text()
    for text in ("Question 1", "Question 2", "School premium", "Your places", "Caveats", "Data provided by Zillow"):
        assert text in page
    assert report.highlights(tmp_path / "absent.toml") == []
