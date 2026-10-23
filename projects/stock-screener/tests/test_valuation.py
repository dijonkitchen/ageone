import shutil
from datetime import date

import pandas as pd
import pytest
import synthetic

from screener import prices, store, valuation
from screener.screen import Filter, Screen, Weight

FAST, BLK = 900001, 2012383
QUOTES = pd.DataFrame({"ticker": ["FAST", "SLOW", "DEBT", "BLK"], "price": [50.0, 20.0, 5.0, 1137.29], "currency": ["USD"] * 4})


def latest(con, cik):
    frame = con.execute("select metric, value from metric_values where cik = ? and fiscal_year = "
                        "(select max(fiscal_year) from metric_values where cik = ?)", [cik, cik]).fetchdf()
    return dict(zip(frame["metric"], frame["value"]))


def test_live_ratio_formulas(con):
    live = valuation.live_ratios(con, QUOTES).set_index("ticker")
    row, m = live.loc["FAST"], latest(con, FAST)
    _, truth = synthetic.build(growth=0.15)
    t = truth[2024]
    assert row["live.fiscal_year"] == 2024
    assert row["live.market_cap"] == pytest.approx(50 * t["shares"], rel=1e-6)
    assert row["live.pe"] == pytest.approx(50 / m["eps"])
    assert row["live.pb"] == pytest.approx(50 / (t["equity"] / t["shares"]), rel=1e-6)
    assert row["live.ptb"] == pytest.approx(50 / ((t["equity"] - t["goodwill"]) / t["shares"]), rel=1e-6)
    assert row["live.ps"] == pytest.approx(50 / m["revenue_ps"])
    assert row["live.pfcf"] == pytest.approx(50 / m["fcf_ps"])
    assert row["live.earnings_yield"] == pytest.approx(m["eps"] / 50)
    assert row["live.fcf_yield"] == pytest.approx(m["fcf_ps"] / 50)
    assert row["live.dividend_yield"] == pytest.approx(m["dps"] / 50)
    ev = 50 * t["shares"] + t["debt"] - t["cash"]
    assert row["live.ev_ebit"] == pytest.approx(ev / t["operating"], rel=1e-6)


def test_ratios_empty_where_they_mean_nothing(con):
    live = valuation.live_ratios(con, QUOTES).set_index("ticker")
    # DEBT has negative book value: no P/B, but a market cap.
    assert pd.isna(live.loc["DEBT", "live.pb"]) and live.loc["DEBT", "live.market_cap"] > 0


def test_currency_mismatch_and_depositary_receipts_are_flagged(db_path, tmp_path):
    path = tmp_path / "copy.duckdb"
    shutil.copy(db_path, path)
    con = store.connect(path)
    con.execute("update companies set latest_form = '20-F' where ticker = 'SLOW'")
    quotes = QUOTES.assign(currency=["EUR", "USD", "USD", "USD"])
    live = valuation.live_ratios(con, quotes).set_index("ticker")
    assert live.loc["FAST", "price_flag"] == "filings in USD, price in EUR"
    assert "depositary receipts" in live.loc["SLOW", "price_flag"]
    assert live.loc[["FAST", "SLOW"], ["live.pe", "live.pb", "live.market_cap"]].isna().all().all()
    assert pd.isna(live.loc["BLK", "price_flag"]) and live.loc["BLK", "live.pe"] > 0


def test_live_ratios_in_screens(con):
    screen = Screen(window="10", filters=[Filter("live.pb", "<=", 8.0), Filter("bvps.cagr", ">=", 0.0)],
                    score=[Weight("live.earnings_yield")], sort_by="score")
    results = screen.run(con, QUOTES)
    # SLOW trades at 9.6 times book; BlackRock has the highest earnings yield.
    assert results["ticker"].tolist() == ["BLK", "FAST"]
    assert "price_flag" in results and "live.pb" in results
    # Lower P/E ranks higher by default; without quotes the live columns are empty and nothing passes.
    ranked = Screen(window="all", score=[Weight("live.pe")]).run(con, QUOTES).set_index("ticker")
    assert ranked["score"].idxmax() == "BLK"
    assert Screen(window="10", filters=[Filter("live.pb", "<=", 8.0)]).run(con).empty
    assert Screen.loads(screen.dumps()) == screen


def test_filing_date_pricing():
    history = pd.DataFrame({"date": pd.to_datetime(["2024-02-15", "2024-02-16", "2024-02-20"]), "close": [10.0, 11.0, 12.0]})
    filings = pd.DataFrame({"fiscal_year": [2021, 2022, 2023], "first_filed": ["2024-02-16", "2024-02-17", None]})
    # Filed on a Saturday: the next trading day's close.
    priced = valuation.filing_date_prices(filings.assign(first_filed=["2024-02-15", "2024-02-17", None]), history)
    assert priced.to_dict() == {2021: 10.0, 2022: 12.0}
    assert valuation.filing_date_prices(filings, history)[2021] == 11.0


def test_historical_ratios_at_first_filing_dates(con, prices_dir):
    provider = prices.RecordedProvider(prices_dir)
    history = provider.history(["FAST"], date(2011, 1, 1), date(2026, 1, 1))
    frame = valuation.historical_ratios(con, FAST, history).set_index("fiscal_year")
    assert len(frame) == 14 and frame["pe"].notna().sum() == 14
    closes = history.set_index("date")["close"]
    # FY2015 was first reported in the 10-K filed 2016-02-15, a Monday.
    assert frame.loc[2015, "price"] == pytest.approx(closes[pd.Timestamp("2016-02-15")])
    eps = con.execute("select value from metric_values where cik = ? and fiscal_year = 2015 and metric = 'eps'", [FAST]).fetchone()[0]
    assert frame.loc[2015, "pe"] == pytest.approx(closes[pd.Timestamp("2016-02-15")] / eps)
    ranges = valuation.ratio_ranges(frame.reset_index(), {"live.pe": 53.2}).set_index("ratio")
    assert ranges.loc["P/E", "years"] == 10 and ranges.loc["P/E", "today"] == 53.2
    last10 = frame["pe"].tail(10)
    assert ranges.loc["P/E", ["low", "median", "high"]].tolist() == pytest.approx([last10.min(), last10.median(), last10.max()])


def test_recorded_blackrock_prices(con):
    provider = prices.RecordedProvider(pytest.importorskip("conftest").PRICES)
    history = provider.history(["BLK"], date(2011, 1, 1), date(2026, 12, 31))
    assert len(history) > 3500
    frame = valuation.historical_ratios(con, BLK, history).set_index("fiscal_year")
    # BlackRock's FY2025 10-K was filed 2026-02-25.
    assert frame.loc[2025, "price"] == pytest.approx(history.set_index("date")["close"][pd.Timestamp("2026-02-25")])
    assert frame.loc[2025, "dividend_yield"] == pytest.approx(20.84 / frame.loc[2025, "price"])
