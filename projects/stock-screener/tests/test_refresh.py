import synthetic

from screener import pipeline, store
from screener.sec import RateLimiter, latest_annual_filing


class FakeSec:
    """Stands in for SecClient: counts requests, serves the synthetic company."""

    def __init__(self):
        self.requests_made = 0
        self.filings = [("10-K", "2024-02-15", "0000999999-24-000001")]

    def tickers(self):
        self.requests_made += 1
        return [{"cik": 999999, "name": "Example", "ticker": "EXMP", "exchange": "NYSE"},
                {"cik": 999998, "name": "Other", "ticker": "OTHR", "exchange": "Nasdaq"}]

    def submissions(self, cik):
        self.requests_made += 1
        form, filed, accession = zip(*self.filings)
        return {"name": "Example", "sic": "3571", "exchanges": ["NYSE"], "fiscalYearEnd": "1231",
                "filings": {"recent": {"form": list(form), "filingDate": list(filed), "accessionNumber": list(accession)}}}

    def company_facts(self, cik):
        self.requests_made += 1
        return synthetic.build()[0]


def test_second_refresh_only_checks_for_changes():
    con = store.connect(":memory:")
    sec = FakeSec()
    counts = pipeline.refresh(sec, con, tickers=["EXMP"], log=lambda m: None)
    assert counts["loaded"] == 1 and sec.requests_made == 3  # tickers, submissions, facts

    sec.requests_made = 0
    counts = pipeline.refresh(sec, con, tickers=["EXMP"], log=lambda m: None)
    assert counts == {"checked": 1, "loaded": 0, "unchanged": 1, "skipped": 0, "failed": 0}
    assert sec.requests_made == 2  # tickers and submissions only

    sec.filings.append(("10-K", "2025-02-14", "0000999999-25-000001"))
    sec.requests_made = 0
    assert pipeline.refresh(sec, con, tickers=["EXMP"], log=lambda m: None)["loaded"] == 1
    row = con.execute("select latest_accession, latest_filed, sic from companies").fetchone()
    assert row == ("0000999999-25-000001", "2025-02-14", "3571")


def test_switching_point_in_time_reloads():
    con = store.connect(":memory:")
    sec = FakeSec()
    pipeline.refresh(sec, con, tickers=["EXMP"], log=lambda m: None)
    assert pipeline.refresh(sec, con, tickers=["EXMP"], pit_mode=True, log=lambda m: None)["loaded"] == 1


def test_rebuild_needs_no_network():
    con = store.connect(":memory:")
    pipeline.refresh(FakeSec(), con, tickers=["EXMP"], log=lambda m: None)
    before = con.execute("select count(*) from stats").fetchone()
    assert pipeline.rebuild(con, log=lambda m: None) == 1
    assert con.execute("select count(*) from stats").fetchone() == before


def test_latest_annual_filing_ignores_quarterlies():
    subs = {"filings": {"recent": {"form": ["10-Q", "10-K", "8-K", "10-K/A"],
                                   "filingDate": ["2025-05-01", "2025-02-01", "2025-06-01", "2025-03-01"],
                                   "accessionNumber": ["a", "b", "c", "d"]}}}
    assert latest_annual_filing(subs) == {"form": "10-K/A", "filed": "2025-03-01", "accession": "d"}


def test_rate_limiter_spaces_requests(monkeypatch):
    clock = {"now": 0.0}
    slept = []
    monkeypatch.setattr("screener.sec.time.monotonic", lambda: clock["now"])
    monkeypatch.setattr("screener.sec.time.sleep", lambda s: slept.append(s))
    limiter = RateLimiter(10)
    for _ in range(5):
        limiter.wait()
    assert slept == [0.1, 0.2, 0.30000000000000004, 0.4]


def test_user_agent_is_required(monkeypatch, tmp_path):
    import pytest

    from screener import config

    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(SystemExit):
        config.load(tmp_path / "none.toml").require_user_agent()
    monkeypatch.setenv("SEC_USER_AGENT", "Jane jane@example.com")
    assert config.load(tmp_path / "none.toml").require_user_agent() == "Jane jane@example.com"
