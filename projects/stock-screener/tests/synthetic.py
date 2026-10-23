"""A made-up company's Company Facts response, built the way real filers report.

Each 10-K reports three years of income and cash flow and two balance sheets.
After a stock split, the next 10-Ks restate earlier years' share counts and
per-share values onto the new basis, and older years stay as first reported,
which is exactly what split adjustment has to undo. The company also restates
one year's revenue, so latest-filed and point-in-time values differ.

Ground truth comes back alongside the facts, on the final (all splits) basis.
"""

from __future__ import annotations

from typing import Any

YEARS = range(2011, 2025)
SPLITS = {2016: 2.0, 2021: 4.0}  # fiscal year on the new basis -> ratio
TAGGED_SPLITS = {2021}  # the 2016 split is left untagged, so it must be detected
RESTATED_YEAR = 2019  # revenue revised in the following 10-K
RESTATEMENT = 1.02


def accession(year: int) -> str:
    return f"0000999999-{(year + 1) % 100:02d}-{year:06d}"


def build(start_equity: float = 1_000.0e6, growth: float = 0.10, shares_now: float = 800e6) -> tuple[dict[str, Any], dict[int, dict[str, float]]]:
    truth: dict[int, dict[str, float]] = {}
    equity = start_equity
    for i, year in enumerate(YEARS):
        shares = shares_now * (1.01 ** (len(YEARS) - 1 - i))  # steady buybacks, final basis
        revenue = 0.8 * equity
        cost = 0.5 * revenue
        operating = 0.25 * revenue
        interest = 0.02 * equity
        pretax = operating - interest
        tax = 0.21 * pretax
        net = pretax - tax
        dividends = 0.3 * net
        equity_end = equity * (1 + growth) if i else equity
        assets = 2 * equity_end
        truth[year] = {
            "revenue": revenue, "cost": cost, "gross": revenue - cost, "operating": operating, "interest": interest,
            "pretax": pretax, "tax": tax, "net": net, "dividends": dividends, "equity": equity_end, "assets": assets,
            "liabilities": assets - equity_end, "current_assets": 0.4 * assets, "current_liabilities": 0.25 * assets,
            "debt": 0.3 * equity_end, "goodwill": 0.1 * assets, "cash": 0.05 * assets, "ocf": net + 0.1 * revenue, "capex": 0.05 * revenue,
            "shares": shares, "diluted_shares": shares * 1.01,
        }
        equity = equity_end
    return _facts(truth), truth


def _basis(year: int, filing_year: int) -> float:
    """Divide final-basis shares by this to get shares on the basis of a filing for filing_year."""
    out = 1.0
    for split_year, ratio in SPLITS.items():
        if split_year > max(year, filing_year):
            out *= ratio
        elif year < split_year <= filing_year:
            pass  # restated onto the new basis
    return out


def _facts(truth: dict[int, dict[str, float]]) -> dict[str, Any]:
    gaap: dict[str, dict[str, Any]] = {}
    dei: dict[str, dict[str, Any]] = {}

    def add(ns: dict, concept: str, unit: str, fact: dict[str, Any]) -> None:
        ns.setdefault(concept, {"label": concept, "units": {}})["units"].setdefault(unit, []).append(fact)

    for filing_year in YEARS:
        meta = {"accn": accession(filing_year), "fy": filing_year, "fp": "FY", "form": "10-K",
                "filed": f"{filing_year + 1}-02-15"}
        for year in (filing_year - 2, filing_year - 1, filing_year):
            if year not in truth:
                continue
            t = truth[year]
            basis = _basis(year, filing_year)
            duration = {"start": f"{year}-01-01", "end": f"{year}-12-31", **meta}
            revenue = t["revenue"] * (RESTATEMENT if year == RESTATED_YEAR and filing_year > year else 1)
            diluted = t["diluted_shares"] / basis
            for concept, value in (
                ("Revenues", revenue), ("CostOfRevenue", t["cost"]), ("GrossProfit", revenue - t["cost"]),
                ("OperatingIncomeLoss", t["operating"]), ("InterestExpense", t["interest"]),
                ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", t["pretax"]),
                ("IncomeTaxExpenseBenefit", t["tax"]), ("NetIncomeLoss", t["net"]),
                ("NetCashProvidedByUsedInOperatingActivities", t["ocf"]),
                ("PaymentsToAcquirePropertyPlantAndEquipment", t["capex"]), ("PaymentsOfDividends", t["dividends"]),
            ):
                add(gaap, concept, "USD", {**duration, "val": round(value)})
            add(gaap, "WeightedAverageNumberOfDilutedSharesOutstanding", "shares", {**duration, "val": round(diluted)})
            add(gaap, "EarningsPerShareDiluted", "USD/shares", {**duration, "val": round(t["net"] / diluted, 2)})
            add(gaap, "CommonStockDividendsPerShareDeclared", "USD/shares",
                {**duration, "val": round(t["dividends"] / (t["shares"] / basis), 4)})
            if year < filing_year - 1:
                continue
            instant = {"end": f"{year}-12-31", **meta}
            for concept, value in (
                ("Assets", t["assets"]), ("AssetsCurrent", t["current_assets"]), ("Liabilities", t["liabilities"]),
                ("LiabilitiesCurrent", t["current_liabilities"]), ("StockholdersEquity", t["equity"]),
                ("LiabilitiesAndStockholdersEquity", t["assets"]), ("LongTermDebt", t["debt"]), ("Goodwill", t["goodwill"]),
                ("CashAndCashEquivalentsAtCarryingValue", t["cash"]),
            ):
                add(gaap, concept, "USD", {**instant, "val": round(value)})
            add(gaap, "CommonStockSharesOutstanding", "shares", {**instant, "val": round(t["shares"] / basis)})
        add(dei, "EntityCommonStockSharesOutstanding", "shares",
            {"end": f"{filing_year + 1}-02-01", "val": round(truth[filing_year]["shares"]), **meta})
        if filing_year in SPLITS and filing_year in TAGGED_SPLITS:
            add(gaap, "StockholdersEquityNoteStockSplitConversionRatio1", "pure",
                {"end": f"{filing_year}-06-30", "val": SPLITS[filing_year], **meta})
    return {"cik": 999999, "entityName": "Example Compounding Corp", "facts": {"dei": dei, "us-gaap": gaap}}


def prices(seed: int, start: str = "2012-01-02", end: str = "2025-06-30", first: float = 20.0, drift: float = 0.10,
           volatility: float = 0.25, common: float = 0.0, common_seed: int = 0):
    """Daily closes on weekdays (date, close): a random walk in log price, the same every run.

    `common` mixes in a shared market path, so two companies' returns correlate.
    """
    import numpy as np
    import pandas as pd

    dates = pd.bdate_range(start, end)
    own = np.random.default_rng(seed).standard_normal(len(dates))
    market = np.random.default_rng(common_seed).standard_normal(len(dates))
    shocks = np.sqrt(1 - common**2) * own + common * market
    daily = volatility / np.sqrt(252)
    logs = np.log(first) + np.cumsum((drift - volatility**2 / 2) / 252 + daily * shocks)
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": np.exp(logs).round(4)})
