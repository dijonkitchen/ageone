"""One company's view: yearly series, the filings behind them, splits, and gaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb
import pandas as pd


@dataclass
class CompanyReport:
    info: dict[str, Any]
    series: pd.DataFrame  # fiscal_year x metric
    filings: pd.DataFrame
    splits: pd.DataFrame
    gaps: pd.DataFrame


def find_company(con: duckdb.DuckDBPyConnection, ticker_or_cik: str) -> int:
    key = ticker_or_cik.strip().upper()
    if key.isdigit():
        row = con.execute("select cik from companies where cik = ?", [int(key)]).fetchone()
    else:
        row = con.execute("select cik from companies where upper(ticker) = ?", [key]).fetchone()
    if not row:
        raise SystemExit(f"{ticker_or_cik} is not in the database; load it with 'screener refresh --tickers {key}'.")
    return int(row[0])


def company_report(con: duckdb.DuckDBPyConnection, cik: int) -> CompanyReport:
    row = con.execute("select * from companies where cik = ?", [cik]).fetchdf().iloc[0].to_dict()
    info = {k: (None if pd.isna(v) else v) for k, v in row.items()}
    values = con.execute("select fiscal_year, metric, value from metric_values where cik = ?", [cik]).fetchdf()
    series = values.pivot(index="fiscal_year", columns="metric", values="value").sort_index() if len(values) else pd.DataFrame()
    filings = con.execute(
        "select fiscal_year, period_ending, form, accession, filed from filings where cik = ? order by fiscal_year", [cik]
    ).fetchdf()
    filings["url"] = [
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{a.replace('-', '')}/" if a else None for a in filings["accession"]
    ]
    splits = con.execute(
        "select fiscal_year, ratio, source, series from splits where cik = ? order by fiscal_year, series", [cik]
    ).fetchdf()
    gaps = con.execute("select metric, years, missing from gaps where cik = ? order by metric", [cik]).fetchdf()
    return CompanyReport(info, series, filings, splits, gaps)
