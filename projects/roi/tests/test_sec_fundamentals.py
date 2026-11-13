from datetime import date

import pytest

from roi.adapters import (
    SECFundamentals,
    parse_company_facts,
    parse_company_facts_history,
)
from roi.analysis import build_history
from roi.domain import Security


def _usd_annual(val):
    return {
        "units": {
            "USD": [
                {
                    "start": "2022-10-01",
                    "end": "2023-09-30",
                    "val": val,
                    "form": "10-K",
                    "fp": "FY",
                }
            ]
        }
    }


def _usd_instant(val):
    return {
        "units": {
            "USD": [{"end": "2023-09-30", "val": val, "form": "10-K", "fp": "FY"}]
        }
    }


COMPANY_FACTS = {
    "cik": 320193,
    "entityName": "Example Co",
    "facts": {
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {
                            "end": "2023-09-30",
                            "val": 15_000_000_000,
                            "form": "10-K",
                            "fp": "FY",
                        }
                    ]
                }
            }
        },
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "start": "2022-10-01",
                            "end": "2023-09-30",
                            "val": 383_000_000_000,
                            "form": "10-K",
                            "fp": "FY",
                        },
                        # a quarterly point that must be ignored in favor of the annual one
                        {
                            "start": "2023-07-01",
                            "end": "2023-09-30",
                            "val": 90_000_000_000,
                            "form": "10-Q",
                            "fp": "Q4",
                        },
                    ]
                }
            },
            "NetIncomeLoss": _usd_annual(97_000_000_000),
            "NetCashProvidedByUsedInOperatingActivities": _usd_annual(110_000_000_000),
            "PaymentsToAcquirePropertyPlantAndEquipment": _usd_annual(11_000_000_000),
            "CashAndCashEquivalentsAtCarryingValue": _usd_instant(30_000_000_000),
            "StockholdersEquity": _usd_instant(62_000_000_000),
            "LongTermDebt": _usd_instant(95_000_000_000),
            "DebtCurrent": _usd_instant(15_000_000_000),
        },
    },
}


@pytest.mark.criteria("FUN-1")
def test_parse_company_facts_picks_annual_figures() -> None:
    fin = parse_company_facts(COMPANY_FACTS, "AAPL")
    assert fin.period_end == date(2023, 9, 30)
    assert fin.revenue == 383_000_000_000  # the annual point, not the quarterly
    assert fin.net_income == 97_000_000_000
    assert fin.free_cash_flow == 99_000_000_000  # 110 - 11
    assert fin.total_debt == 110_000_000_000  # 95 long + 15 current
    assert fin.net_debt == 80_000_000_000  # 110 - 30
    assert fin.shares_outstanding == 15_000_000_000


def test_parse_raises_on_missing_required_concept() -> None:
    payload: dict[str, object] = {"facts": {"us-gaap": {}, "dei": {}}}
    with pytest.raises(ValueError):
        parse_company_facts(payload, "AAPL")


@pytest.mark.criteria("FUN-5")
def test_adapter_uses_injected_fetch_and_caches() -> None:
    calls = []

    def fetch(url):
        calls.append(url)
        return COMPANY_FACTS

    sec = SECFundamentals(
        user_agent="Tester tester@example.com",
        fetch_json=fetch,
        ticker_map={"AAPL": 320193},
    )
    fin = sec.financials(Security("AAPL"))
    sec.financials(Security("AAPL"))  # cached
    assert fin.revenue == 383_000_000_000
    assert len(calls) == 1
    assert calls[0].endswith("/api/xbrl/companyfacts/CIK0000320193.json")


@pytest.mark.criteria("FUN-5")
def test_adapter_resolves_cik_from_ticker_map_payload() -> None:
    def fetch(url):
        if url == SECFundamentals.TICKERS_URL:
            return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Example Co"}}
        return COMPANY_FACTS

    sec = SECFundamentals(user_agent="Tester tester@example.com", fetch_json=fetch)
    assert sec.financials(Security("aapl")).revenue == 383_000_000_000


def test_adapter_requires_contact_user_agent() -> None:
    with pytest.raises(ValueError):
        SECFundamentals(user_agent="no-contact")


# --- multi-year history ----------------------------------------------------


def _flow(year, val):
    return {
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "val": val,
        "form": "10-K",
        "fp": "FY",
        "filed": f"{year + 1}-02-15",
    }


def _instant(year, val):
    return {
        "end": f"{year}-12-31",
        "val": val,
        "form": "10-K",
        "fp": "FY",
        "filed": f"{year + 1}-02-15",
    }


def _flows(unit, by_year):
    return {"units": {unit: [_flow(y, v) for y, v in by_year.items()]}}


def _instants(by_year):
    return {"units": {"USD": [_instant(y, v) for y, v in by_year.items()]}}


# 10% per-year growth in revenue, net income, OCF; flat 10 diluted shares.
MULTI_YEAR_FACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": _flows("USD", {2021: 1000, 2022: 1100, 2023: 1210}),
            "NetIncomeLoss": _flows("USD", {2021: 100, 2022: 110, 2023: 121}),
            "NetCashProvidedByUsedInOperatingActivities": _flows(
                "USD", {2021: 150, 2022: 165, 2023: 181.5}
            ),
            "PaymentsToAcquirePropertyPlantAndEquipment": _flows(
                "USD", {2021: 50, 2022: 55, 2023: 60.5}
            ),
            "WeightedAverageNumberOfDilutedSharesOutstanding": _flows(
                "shares", {2021: 10, 2022: 10, 2023: 10}
            ),
            "StockholdersEquity": _instants({2021: 500, 2022: 550, 2023: 605}),
            "CashAndCashEquivalentsAtCarryingValue": _instants(
                {2021: 80, 2022: 80, 2023: 80}
            ),
            "LongTermDebt": _instants({2021: 200, 2022: 200, 2023: 200}),
        }
    }
}


@pytest.mark.criteria("FUN-7")
def test_parse_history_builds_one_record_per_year() -> None:
    history = parse_company_facts_history(MULTI_YEAR_FACTS, "X")
    assert [f.period_end.year for f in history] == [2021, 2022, 2023]
    assert [f.revenue for f in history] == [1000, 1100, 1210]
    assert history[-1].free_cash_flow == pytest.approx(121.0)  # 181.5 - 60.5


@pytest.mark.criteria("FUN-7")
def test_parse_history_respects_year_window() -> None:
    assert len(parse_company_facts_history(MULTI_YEAR_FACTS, "X", years=2)) == 2


def test_history_feeds_per_share_growth() -> None:
    sec = SECFundamentals(
        user_agent="Tester tester@example.com",
        fetch_json=lambda url: MULTI_YEAR_FACTS,
        ticker_map={"X": 1},
    )
    hist = build_history(sec.history(Security("X")))
    revenue = hist.summaries["revenue"]
    assert revenue.per_share == (100.0, 110.0, 121.0)  # /10 shares
    assert revenue.median_growth == pytest.approx(0.1)
    assert hist.summaries["earnings"].median_growth == pytest.approx(0.1)
