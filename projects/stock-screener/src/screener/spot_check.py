"""Spot check: compare loaded values with numbers read from 10-K filings."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import duckdb

from .company import find_company


def run(con: duckdb.DuckDBPyConnection, path: Path, log=print) -> bool:
    spec = tomllib.loads(Path(path).read_text())
    tolerance = float(spec.get("tolerance", 0.01))
    ok = True
    for company in spec.get("companies", []):
        try:
            cik = find_company(con, company["ticker"])
        except SystemExit as missing:
            log(f"MISSING {company['ticker']}: {missing}")
            ok = False
            continue
        for metric, expected in company.get("values", {}).items():
            for year, want in expected.items():
                row = con.execute(
                    "select value from metric_values where cik = ? and metric = ? and fiscal_year = ?",
                    [cik, metric, int(year)],
                ).fetchone()
                got = row[0] if row else math.nan
                good = not math.isnan(got) and abs(got - want) <= tolerance * abs(want)
                ok &= good
                log(f"{'ok  ' if good else 'FAIL'} {company['ticker']} {metric} {year}: expected {want}, got {got:.4g}")
    return ok
