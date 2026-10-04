"""The DuckDB database: one file with statements, metrics, stats, and the screen table."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

SCHEMA = """
create table if not exists meta (key varchar primary key, value varchar);
create table if not exists companies (
    cik bigint primary key,
    ticker varchar,
    name varchar,
    exchange varchar,
    sic varchar,
    sic_description varchar,
    fiscal_year_end varchar,
    company_type varchar,
    currency varchar,
    latest_accession varchar,
    latest_form varchar,
    latest_filed varchar,
    first_fiscal_year integer,
    last_fiscal_year integer,
    checked_at timestamp,
    loaded_at timestamp,
    status varchar
);
create table if not exists line_items (
    cik bigint, fiscal_year integer, period_ending varchar, statement varchar, tag varchar,
    value double, unit varchar, currency varchar, source varchar
);
create table if not exists split_facts (cik bigint, "end" varchar, ratio double, accession varchar, filed varchar, concept varchar);
create table if not exists filings (cik bigint, fiscal_year integer, period_ending varchar, accession varchar, form varchar, filed varchar);
create table if not exists splits (cik bigint, fiscal_year integer, ratio double, source varchar, series varchar);
create table if not exists metric_values (cik bigint, fiscal_year integer, metric varchar, value double);
create table if not exists stats (cik bigint, "window" varchar, metric varchar, stat varchar, value double);
create table if not exists gaps (cik bigint, metric varchar, years integer, missing varchar);
"""

PER_COMPANY_TABLES = ("line_items", "split_facts", "filings", "splits", "metric_values", "stats", "gaps")


def connect(path: Path | str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if read_only and str(path) != ":memory:" and not Path(path).exists():
        raise SystemExit(f"No database at {path}. Run 'screener refresh' first.")
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        con.execute(SCHEMA)
    return con


def get_meta(con: duckdb.DuckDBPyConnection, key: str) -> str | None:
    row = con.execute("select value from meta where key = ?", [key]).fetchone()
    return row[0] if row else None


def set_meta(con: duckdb.DuckDBPyConnection, key: str, value: str) -> None:
    con.execute("insert or replace into meta values (?, ?)", [key, value])


def replace_company_rows(con: duckdb.DuckDBPyConnection, cik: int, tables: dict[str, pd.DataFrame]) -> None:
    """Swap one company's rows in the given tables in one transaction."""
    con.execute("begin")
    try:
        for table, frame in tables.items():
            assert table in PER_COMPANY_TABLES, table
            con.execute(f"delete from {table} where cik = ?", [cik])
            if frame is not None and not frame.empty:
                columns = [c for c in con.table(table).columns if c != "cik"]
                staged = frame.assign(cik=cik)[["cik", *columns]]  # noqa: F841 (read by DuckDB)
                con.execute(f"insert into {table} select * from staged")
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise


def upsert_company(con: duckdb.DuckDBPyConnection, row: dict) -> None:
    columns = con.table("companies").columns
    existing = con.execute("select * from companies where cik = ?", [row["cik"]]).fetchdf()
    merged = existing.iloc[0].to_dict() if len(existing) else {c: None for c in columns}
    merged.update({k: v for k, v in row.items() if k in columns})
    values = [None if pd.api.types.is_scalar(merged[c]) and pd.isna(merged[c]) else merged[c] for c in columns]
    con.execute(f"insert or replace into companies values ({', '.join('?' * len(columns))})", values)
