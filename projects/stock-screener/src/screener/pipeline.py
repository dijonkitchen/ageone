"""Full load and incremental refresh from SEC EDGAR into the database."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

import duckdb
import pandas as pd

from . import metrics, store
from .sec import NotFound, SecClient, company_profile, latest_annual_filing
from .standardize import standardize

Log = Callable[[str], None]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def derive(con: duckdb.DuckDBPyConnection, cik: int, line_items: pd.DataFrame, split_facts: pd.DataFrame) -> None:
    """Recompute one company's splits, metrics, stats, and gaps from its stored line items."""
    result = metrics.compute(line_items, split_facts)
    splits = pd.DataFrame(
        [{"fiscal_year": s.fiscal_year, "ratio": s.ratio, "source": s.source, "series": s.series} for s in result.splits],
        columns=["fiscal_year", "ratio", "source", "series"],
    )
    store.replace_company_rows(con, cik, {
        "splits": splits,
        "metric_values": result.values[["fiscal_year", "metric", "value"]],
        "stats": metrics.window_stats(result.values),
        "gaps": result.gaps,
    })


def load_company(
    con: duckdb.DuckDBPyConnection, cik: int, facts_json: dict[str, Any], company: dict[str, Any], pit_mode: bool
) -> None:
    std = standardize(facts_json, pit_mode=pit_mode)
    items = std.line_items
    store.replace_company_rows(con, cik, {
        "line_items": items,
        "split_facts": std.split_facts,
        "filings": std.filings,
    })
    derive(con, cik, items, std.split_facts)
    years = items["fiscal_year"] if len(items) else pd.Series(dtype=int)
    store.upsert_company(con, {
        **company,
        "cik": cik,
        "name": company.get("name") or std.entity_name,
        "company_type": std.company_type,
        "currency": std.currency,
        "first_fiscal_year": int(years.min()) if len(years) else None,
        "last_fiscal_year": int(years.max()) if len(years) else None,
        "loaded_at": _now(),
        "status": "loaded" if len(items) else "no annual statements",
    })


def rebuild(con: duckdb.DuckDBPyConnection, log: Log = print) -> int:
    """Recompute metrics and stats for every company from stored statements (no network)."""
    ciks = [r[0] for r in con.execute("select distinct cik from line_items order by cik").fetchall()]
    for cik in ciks:
        items = con.execute("select * exclude (cik) from line_items where cik = ?", [cik]).fetchdf()
        split_facts = con.execute("select * exclude (cik) from split_facts where cik = ?", [cik]).fetchdf()
        derive(con, cik, items, split_facts)
    log(f"rebuilt metrics for {len(ciks)} companies")
    return len(ciks)


def _companies(client: SecClient, tickers: Iterable[str] | None) -> list[dict[str, Any]]:
    wanted = {t.upper() for t in tickers} if tickers else None
    by_cik: dict[int, dict[str, Any]] = {}
    for row in client.tickers():
        ticker = (row.get("ticker") or "").upper()
        if wanted is not None and ticker not in wanted:
            continue
        # The SEC lists a company's primary ticker first.
        by_cik.setdefault(int(row["cik"]), {"ticker": ticker, "name": row.get("name"), "exchange": row.get("exchange")})
    if wanted:
        missing = wanted - {c["ticker"] for c in by_cik.values()}
        if missing:
            print(f"not in the SEC ticker list: {', '.join(sorted(missing))}", file=sys.stderr)
    return [{"cik": cik, **info} for cik, info in sorted(by_cik.items())]


def _facts(client: SecClient, cik: int, ticker: str) -> dict[str, Any]:
    from openbb_sec.utils import company_facts as obb

    ciks = [int(c) for c in obb.MULTI_CIK_TICKERS.get(ticker, [])] or [cik]
    responses = [client.company_facts(c) for c in ciks]
    if len(responses) == 1:
        return responses[0]
    # Same merge OpenBB uses for companies that changed CIK (GOOG, BLK, ...).
    return {"entityName": responses[0].get("entityName", ""), "cik": responses[0].get("cik", ""),
            "facts": obb._schema.merge_facts(*responses)}


def refresh(
    client: SecClient,
    con: duckdb.DuckDBPyConnection,
    tickers: Iterable[str] | None = None,
    full: bool = False,
    pit_mode: bool | None = None,
    limit: int | None = None,
    workers: int = 4,
    log: Log = print,
) -> dict[str, int]:
    """Check each company's latest annual filing and load the ones that changed."""
    stored_pit = store.get_meta(con, "pit_mode")
    pit = (stored_pit == "true") if pit_mode is None else pit_mode
    if stored_pit is not None and (stored_pit == "true") != pit:
        log("point-in-time mode changed: reloading every company")
        full = True
    store.set_meta(con, "pit_mode", "true" if pit else "false")

    companies = _companies(client, tickers)
    if limit:
        companies = companies[:limit]
    known = dict(con.execute("select cik, latest_accession from companies").fetchall())

    def check(company: dict[str, Any]) -> tuple[dict[str, Any], dict | None, dict | None, str | None]:
        cik = company["cik"]
        try:
            subs = client.submissions(cik)
        except NotFound:
            return company, None, None, "no submissions"
        latest = latest_annual_filing(subs)
        profile = company_profile(subs)
        info = {**company, **{k: v for k, v in profile.items() if k != "exchanges"}}
        info["exchange"] = company.get("exchange") or ", ".join(profile["exchanges"]) or None
        if latest is None:
            return info, latest, None, "no annual filings"
        if not full and known.get(cik) == latest["accession"]:
            return info, latest, None, "unchanged"
        try:
            return info, latest, _facts(client, cik, company["ticker"]), None
        except NotFound:
            return info, latest, None, "no XBRL facts"

    counts = {"checked": 0, "loaded": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(check, c) for c in companies]
        for done, future in enumerate(as_completed(futures), 1):
            counts["checked"] += 1
            try:
                info, latest, facts, reason = future.result()
            except Exception as error:  # noqa: BLE001 (one bad company never stops the run)
                counts["failed"] += 1
                log(f"failed: {error}")
                continue
            row = {**info, "checked_at": _now()}
            if latest:
                row.update(latest_accession=latest["accession"], latest_form=latest["form"], latest_filed=latest["filed"])
            if facts is None:
                key = "unchanged" if reason == "unchanged" else "skipped"
                counts[key] += 1
                if reason != "unchanged":
                    row["status"] = reason
                store.upsert_company(con, row)
            else:
                try:
                    load_company(con, info["cik"], facts, row, pit)
                    counts["loaded"] += 1
                except Exception as error:  # noqa: BLE001
                    counts["failed"] += 1
                    log(f"failed {info.get('ticker')}: {error}")
            if done % 100 == 0 or done == len(futures):
                log(f"{done}/{len(futures)} checked, {counts['loaded']} loaded, {client.requests_made} requests")
    store.set_meta(con, "refreshed_at", _now().isoformat(timespec="seconds"))
    return counts
