"""Company Facts -> standardized annual line items, gap fills, split ratios, and filings.

OpenBB's SEC provider does the hard part (tag chains, company types, identities,
restatements); this module calls it on a Company Facts response and adds what
it doesn't keep: line items from gap_fill.toml, split ratio facts, and which
filing each fiscal year came from.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from typing import Any

import pandas as pd
from openbb_sec.utils.company_facts import resolve_company_facts

from .sec import ANNUAL_FORMS

STATEMENTS = ("income_statement", "balance_sheet", "cash_flow")
LINE_ITEM_COLUMNS = ["fiscal_year", "period_ending", "statement", "tag", "value", "unit", "currency", "source"]


def gap_fill_mapping() -> dict[str, dict[str, Any]]:
    return tomllib.loads(resources.files("screener.data").joinpath("gap_fill.toml").read_text())


@dataclass
class Standardized:
    entity_name: str
    company_type: str
    currency: str
    line_items: pd.DataFrame
    split_facts: pd.DataFrame
    filings: pd.DataFrame
    diagnostics: list[str] = field(default_factory=list)


def _facts_for(facts: dict[str, Any], concept: str) -> tuple[str, list[dict[str, Any]]]:
    namespace, _, name = concept.partition(":")
    units = facts.get(namespace, {}).get(name, {}).get("units", {})
    for unit, rows in units.items():
        return unit, rows
    return "", []


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def _pick(rows: list[dict[str, Any]], pit_mode: bool) -> dict[str, Any]:
    """Latest filed fact wins (restated values), or the first filed one in point-in-time mode."""
    key = lambda r: (r.get("filed", ""), r.get("accn", ""))
    return min(rows, key=key) if pit_mode else max(rows, key=key)


def _gap_fill(
    facts: dict[str, Any], year_ends: dict[int, str], pit_mode: bool, currency: str
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    split_facts: list[dict[str, Any]] = []
    for item, spec in gap_fill_mapping().items():
        period = spec.get("period", "instant")
        if period == "any":
            for concept in spec["concepts"]:
                _, found = _facts_for(facts, concept)
                for fact in found:
                    split_facts.append(
                        {"end": fact["end"], "ratio": float(fact["val"]), "accession": fact.get("accn"),
                         "filed": fact.get("filed"), "concept": concept}
                    )
            continue
        max_after = int(spec.get("max_days_after", 0))
        for fiscal_year, year_end in year_ends.items():
            for concept in spec["concepts"]:
                unit, found = _facts_for(facts, concept)
                candidates = []
                for fact in found:
                    if fact.get("form") not in ANNUAL_FORMS or fact.get("val") is None:
                        continue
                    if period == "instant":
                        if "start" in fact or not 0 <= _days(fact["end"], year_end) <= max_after:
                            continue
                    elif "start" not in fact or abs(_days(fact["end"], year_end)) > 7 or not (
                        330 <= _days(fact["end"], fact["start"]) <= 400
                    ):
                        continue
                    candidates.append(fact)
                if candidates:
                    # Closest to year end first, then the filing rule.
                    nearest = min(abs(_days(c["end"], year_end)) for c in candidates)
                    fact = _pick([c for c in candidates if abs(_days(c["end"], year_end)) == nearest], pit_mode)
                    rows.append(
                        {"fiscal_year": fiscal_year, "period_ending": year_end, "statement": "gap_fill",
                         "tag": item, "value": float(fact["val"]),
                         "unit": "shares" if unit == "shares" else ("per_share" if "/" in unit else "monetary"),
                         "currency": currency, "source": f"gap-fill:{concept}"}
                    )
                    break
    splits = pd.DataFrame(split_facts, columns=["end", "ratio", "accession", "filed", "concept"])
    return rows, splits.drop_duplicates(subset=["end", "ratio"]).reset_index(drop=True)


def _filings(facts: dict[str, Any], year_ends: dict[int, str], pit_mode: bool) -> pd.DataFrame:
    """For each fiscal year, the annual filing whose facts end on that year end."""
    by_end: dict[str, list[dict[str, Any]]] = {}
    wanted = set(year_ends.values())
    for namespace in facts.values():
        for concept in namespace.values():
            for rows in concept.get("units", {}).values():
                for fact in rows:
                    if fact.get("end") in wanted and fact.get("form") in ANNUAL_FORMS and fact.get("fp") == "FY":
                        by_end.setdefault(fact["end"], []).append(fact)
    out = []
    for fiscal_year, year_end in sorted(year_ends.items()):
        found = by_end.get(year_end)
        if not found:
            continue
        # The same filing rule as the values: the latest filing reporting that year end
        # (whose restated values win), or the first one in point-in-time mode.
        fact = _pick(found, pit_mode)
        out.append({"fiscal_year": fiscal_year, "period_ending": year_end, "accession": fact.get("accn"),
                    "form": fact.get("form"), "filed": fact.get("filed")})
    return pd.DataFrame(out, columns=["fiscal_year", "period_ending", "accession", "form", "filed"])


def standardize(facts_json: dict[str, Any], pit_mode: bool = False) -> Standardized:
    result = resolve_company_facts(facts_json, period="annual", pit_mode=pit_mode)
    frames = []
    for statement in STATEMENTS:
        records = getattr(result, statement)
        if records:
            frame = pd.DataFrame(records)
            frame = frame[frame["frequency"] == "annual"].assign(statement=statement)
            frames.append(frame)
    if frames:
        items = pd.concat(frames, ignore_index=True)
        items = items[items["fiscal_period"] == "FY"] if "fiscal_period" in items else items
        items = items[LINE_ITEM_COLUMNS].copy()
        items["value"] = pd.to_numeric(items["value"], errors="coerce").astype(float)
        items["fiscal_year"] = items["fiscal_year"].astype(int)
    else:
        items = pd.DataFrame(columns=LINE_ITEM_COLUMNS)

    # One year end per fiscal year: the latest period ending OpenBB assigned to it.
    year_ends = (
        items.groupby("fiscal_year")["period_ending"].max().to_dict() if len(items) else {}
    )
    facts = facts_json.get("facts", {})
    gap_rows, split_facts = _gap_fill(facts, year_ends, pit_mode, result.currency)
    if gap_rows:
        items = pd.concat([items, pd.DataFrame(gap_rows)], ignore_index=True)
    items = items.dropna(subset=["value"]).drop_duplicates(subset=["fiscal_year", "statement", "tag"], keep="last")
    return Standardized(
        entity_name=result.entity_name,
        company_type=result.company_type,
        currency=result.currency,
        line_items=items.sort_values(["fiscal_year", "statement", "tag"]).reset_index(drop=True),
        split_facts=split_facts,
        filings=_filings(facts, year_ends, pit_mode),
        diagnostics=[str(d) for d in result.diagnostics],
    )
