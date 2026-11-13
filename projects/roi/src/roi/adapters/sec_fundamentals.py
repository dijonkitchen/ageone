"""SEC EDGAR fundamentals adapter (Spec 0004).

Reads the SEC's keyless ``companyfacts`` XBRL API. The only dependency is the
standard library; network access is isolated behind an injectable fetcher and
the XBRL->Financials mapping (`parse_company_facts`) is pure, so tests run
offline against a fixture.

SEC fair-access policy requires a descriptive ``User-Agent`` with contact info,
e.g. ``"Jane Doe jane@example.com"``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from ..domain import Financials, Security

# XBRL concepts, in preference order. The first that resolves wins.
_REVENUE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
_NET_INCOME = ("NetIncomeLoss",)
_OCF = (
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
)
_CAPEX = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
)
_CASH = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
)
_EQUITY = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
_LONG_TERM_DEBT = ("LongTermDebtNoncurrent", "LongTermDebt")
_SHORT_TERM_DEBT = ("LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings")
_SHARES_DEI = ("EntityCommonStockSharesOutstanding",)
_SHARES_GAAP = ("CommonStockSharesOutstanding",)
# Per-share *history* uses the period-aligned weighted-average diluted count,
# which is the correct denominator for year-by-year per-share figures.
_DILUTED_SHARES = (
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
    "WeightedAverageNumberOfSharesOutstandingBasic",
)


def _duration_days(point: dict[str, Any]) -> int:
    start = date.fromisoformat(point["start"])
    end = date.fromisoformat(point["end"])
    return (end - start).days


def _latest_annual(concept: dict[str, Any], unit: str) -> tuple[float, str] | None:
    """Pick the most recent ~annual value reported on a 10-K."""
    points = concept.get("units", {}).get(unit, [])
    tens = [p for p in points if str(p.get("form", "")).startswith("10-K")] or points
    if not tens:
        return None
    flows = [p for p in tens if p.get("start")]
    if flows:
        annual = [p for p in flows if 300 <= _duration_days(p) <= 400]
        pool = annual or flows
    else:
        pool = tens  # instant (balance-sheet) values have no start
    best = max(pool, key=lambda p: p.get("end", ""))
    return float(best["val"]), str(best["end"])


def _pick(
    namespace: dict[str, Any], concepts: Sequence[str], unit: str
) -> tuple[float, str] | None:
    for name in concepts:
        concept = namespace.get(name)
        if concept:
            found = _latest_annual(concept, unit)
            if found is not None:
                return found
    return None


def _annual_by_end(concept: dict[str, Any], unit: str) -> dict[str, float]:
    """Map every annual 10-K data point to ``{period_end: value}``.

    Income-statement and cash-flow filings report several years at once, so this
    yields a multi-year series. When the same period is restated across filings,
    the most recently filed value wins.
    """
    points = concept.get("units", {}).get(unit, [])
    tens = [p for p in points if str(p.get("form", "")).startswith("10-K")] or points
    best: dict[str, tuple[str, float]] = {}
    for p in tens:
        if p.get("start") and not (300 <= _duration_days(p) <= 400):
            continue
        end = str(p.get("end", ""))
        filed = str(p.get("filed", ""))
        if end not in best or filed > best[end][0]:
            best[end] = (filed, float(p["val"]))
    return {end: value for end, (_filed, value) in best.items()}


def _concept_series(
    namespace: dict[str, Any], concepts: Sequence[str], unit: str
) -> dict[str, float]:
    for name in concepts:
        concept = namespace.get(name)
        if concept:
            series = _annual_by_end(concept, unit)
            if series:
                return series
    return {}


def parse_company_facts_history(
    payload: dict[str, Any], symbol: str, *, years: int = 10
) -> list[Financials]:
    """Map an EDGAR ``companyfacts`` payload to up to ``years`` of annual
    :class:`Financials`, one per fiscal year that has the required figures."""
    gaap = payload.get("facts", {}).get("us-gaap", {})

    revenue = _concept_series(gaap, _REVENUE, "USD")
    net_income = _concept_series(gaap, _NET_INCOME, "USD")
    ocf = _concept_series(gaap, _OCF, "USD")
    capex = _concept_series(gaap, _CAPEX, "USD")
    cash = _concept_series(gaap, _CASH, "USD")
    equity = _concept_series(gaap, _EQUITY, "USD")
    long_debt = _concept_series(gaap, _LONG_TERM_DEBT, "USD")
    short_debt = _concept_series(gaap, _SHORT_TERM_DEBT, "USD")
    shares = _concept_series(gaap, _DILUTED_SHARES, "shares")

    history: list[Financials] = []
    for end in sorted(revenue):
        if not all(end in series for series in (net_income, ocf, equity, shares)):
            continue  # skip a year missing a required figure
        history.append(
            Financials(
                symbol=symbol,
                period_end=date.fromisoformat(end),
                revenue=revenue[end],
                net_income=net_income[end],
                operating_cash_flow=ocf[end],
                capital_expenditures=capex.get(end, 0.0),
                total_debt=long_debt.get(end, 0.0) + short_debt.get(end, 0.0),
                cash_and_equivalents=cash.get(end, 0.0),
                shareholders_equity=equity[end],
                shares_outstanding=shares[end],
            )
        )
    return history[-years:]


def parse_company_facts(payload: dict[str, Any], symbol: str) -> Financials:
    """Map an EDGAR ``companyfacts`` payload to a :class:`Financials`."""
    facts = payload.get("facts", {})
    gaap = facts.get("us-gaap", {})
    dei = facts.get("dei", {})

    revenue = _pick(gaap, _REVENUE, "USD")
    net_income = _pick(gaap, _NET_INCOME, "USD")
    ocf = _pick(gaap, _OCF, "USD")
    capex = _pick(gaap, _CAPEX, "USD")
    cash = _pick(gaap, _CASH, "USD")
    equity = _pick(gaap, _EQUITY, "USD")
    long_debt = _pick(gaap, _LONG_TERM_DEBT, "USD")
    short_debt = _pick(gaap, _SHORT_TERM_DEBT, "USD")
    shares = _pick(dei, _SHARES_DEI, "shares") or _pick(gaap, _SHARES_GAAP, "shares")

    def required(value: tuple[float, str] | None, label: str) -> tuple[float, str]:
        if value is None:
            raise ValueError(f"{symbol}: SEC facts missing {label}")
        return value

    revenue = required(revenue, "revenue")
    net_income = required(net_income, "net income")
    ocf = required(ocf, "operating cash flow")
    equity = required(equity, "shareholders equity")
    shares = required(shares, "shares outstanding")

    total_debt = (long_debt[0] if long_debt else 0.0) + (
        short_debt[0] if short_debt else 0.0
    )
    return Financials(
        symbol=symbol,
        period_end=date.fromisoformat(revenue[1]),
        revenue=revenue[0],
        net_income=net_income[0],
        operating_cash_flow=ocf[0],
        capital_expenditures=capex[0] if capex else 0.0,
        total_debt=total_debt,
        cash_and_equivalents=cash[0] if cash else 0.0,
        shareholders_equity=equity[0],
        shares_outstanding=shares[0],
    )


class SECFundamentals:
    """Fetches financials from SEC EDGAR. Implements ``FundamentalsProvider``."""

    BASE = "https://data.sec.gov"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    def __init__(
        self,
        *,
        user_agent: str,
        fetch_json: Callable[[str], Any] | None = None,
        ticker_map: dict[str, int] | None = None,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a contact User-Agent, e.g. 'Jane Doe jane@example.com'"
            )
        self._user_agent = user_agent
        self._fetch = fetch_json or self._default_fetch
        self._ticker_map = (
            {k.upper(): v for k, v in ticker_map.items()} if ticker_map else None
        )
        self._facts_cache: dict[str, Any] = {}

    def _default_fetch(self, url: str) -> Any:
        import json
        import urllib.request

        request = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())

    def _cik_for(self, symbol: str) -> int:
        if self._ticker_map is None:
            payload = self._fetch(self.TICKERS_URL)
            self._ticker_map = {
                str(row["ticker"]).upper(): int(row["cik_str"])
                for row in payload.values()
            }
        try:
            return self._ticker_map[symbol.upper()]
        except KeyError as exc:
            raise LookupError(f"no SEC CIK found for {symbol}") from exc

    def _company_facts(self, symbol: str) -> Any:
        cached = self._facts_cache.get(symbol)
        if cached is not None:
            return cached
        cik = self._cik_for(symbol)
        url = f"{self.BASE}/api/xbrl/companyfacts/CIK{cik:010d}.json"
        payload = self._fetch(url)
        self._facts_cache[symbol] = payload
        return payload

    def financials(self, security: Security) -> Financials:
        return parse_company_facts(
            self._company_facts(security.symbol), security.symbol
        )

    def history(self, security: Security, *, years: int = 10) -> list[Financials]:
        return parse_company_facts_history(
            self._company_facts(security.symbol), security.symbol, years=years
        )
