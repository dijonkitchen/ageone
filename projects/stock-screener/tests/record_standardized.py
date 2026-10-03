"""Regenerate the recorded standardized output after a reviewed OpenBB upgrade."""

import gzip
import json
from pathlib import Path

from screener.standardize import standardize

FIXTURES = Path(__file__).parent / "fixtures"

for path in sorted(FIXTURES.glob("*.companyfacts.json.gz")):
    ticker = path.name.split(".")[0]
    std = standardize(json.loads(gzip.decompress(path.read_bytes())))
    std.line_items.to_csv(FIXTURES / f"{ticker}.standardized.csv", index=False)
    print(f"wrote {ticker}.standardized.csv ({len(std.line_items)} rows)")
