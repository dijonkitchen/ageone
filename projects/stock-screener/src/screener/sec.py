"""SEC EDGAR client that follows the fair access rules.

Every request sends the configured User-Agent, waits so there are at most
`requests_per_second` requests per second across threads, and backs off
exponentially on rate limiting, server errors, and dropped connections.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Forms whose filing can change annual numbers.
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}


class NotFound(Exception):
    """The SEC has no such document (for example, a company with no XBRL facts)."""


class RateLimiter:
    def __init__(self, per_second: float):
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_at - now
            self.next_at = max(now, self.next_at) + self.interval
        if delay > 0:
            time.sleep(delay)


class SecClient:
    def __init__(self, user_agent: str, requests_per_second: float = 8.0, retries: int = 5):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.limiter = RateLimiter(requests_per_second)
        self.retries = retries
        self.requests_made = 0

    def get_json(self, url: str) -> Any:
        for attempt in range(self.retries + 1):
            self.limiter.wait()
            self.requests_made += 1
            try:
                response = self.session.get(url, timeout=60)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.retries:
                    raise
            else:
                if response.status_code == 404:
                    raise NotFound(url)
                if response.status_code not in (403, 429) and response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                if attempt == self.retries:
                    response.raise_for_status()
            time.sleep(min(60, 2 ** (attempt + 1)))
        raise RuntimeError("unreachable")

    def tickers(self) -> list[dict[str, Any]]:
        """Every listed company: cik, name, ticker, exchange."""
        data = self.get_json(TICKERS_URL)
        fields = data["fields"]
        return [dict(zip(fields, row)) for row in data["data"]]

    def submissions(self, cik: int) -> dict[str, Any]:
        return self.get_json(SUBMISSIONS_URL.format(cik=cik))

    def company_facts(self, cik: int) -> dict[str, Any]:
        return self.get_json(FACTS_URL.format(cik=cik))


def latest_annual_filing(submissions: dict[str, Any]) -> dict[str, str] | None:
    """The most recent filing that can change annual numbers, from a submissions response."""
    recent = submissions.get("filings", {}).get("recent", {})
    best = None
    for form, filed, accession in zip(
        recent.get("form", []), recent.get("filingDate", []), recent.get("accessionNumber", [])
    ):
        if form in ANNUAL_FORMS and (best is None or (filed, accession) > (best["filed"], best["accession"])):
            best = {"form": form, "filed": filed, "accession": accession}
    return best


def company_profile(submissions: dict[str, Any]) -> dict[str, Any]:
    """Name, SIC industry, exchanges, and fiscal year end from a submissions response."""
    return {
        "name": submissions.get("name"),
        "sic": submissions.get("sic") or None,
        "sic_description": submissions.get("sicDescription") or None,
        "exchanges": [e for e in submissions.get("exchanges", []) if e],
        "fiscal_year_end": submissions.get("fiscalYearEnd") or None,
    }
