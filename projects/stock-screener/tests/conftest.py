import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import synthetic

from screener import pipeline, store

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(ticker: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / f"{ticker}.companyfacts.json.gz").read_bytes()))


@pytest.fixture(scope="session")
def blk_facts() -> dict:
    return load_fixture("BLK")


def build_db(path) -> object:
    """Four companies: two synthetic compounders, a shrinking one with negative equity, and BlackRock."""
    con = store.connect(path)
    companies = [
        (900001, "FAST", "NYSE", {"growth": 0.15}),
        (900002, "SLOW", "Nasdaq", {"growth": 0.04}),
        (900003, "DEBT", "NYSE", {"growth": -0.5, "start_equity": -50e6}),
    ]
    for cik, ticker, exchange, kwargs in companies:
        facts, _ = synthetic.build(**kwargs)
        pipeline.load_company(con, cik, facts, {"ticker": ticker, "exchange": exchange, "sic": "3571"}, pit_mode=False)
    pipeline.load_company(con, 2012383, load_fixture("BLK"), {"ticker": "BLK", "exchange": "NYSE", "sic": "6211"}, False)
    return con


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "screener.duckdb"
    build_db(path).close()
    return path


@pytest.fixture
def con(db_path):
    con = store.connect(db_path, read_only=True)
    yield con
    con.close()
