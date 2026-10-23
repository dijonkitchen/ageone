from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "src" / "screener" / "app.py")


def _app(db_path, prices_dir=None):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = "Screen"
    import sys

    sys.argv = ["app.py", "--db", str(db_path), *(["--prices-dir", str(prices_dir)] if prices_dir else [])]
    return at


def test_screen_page_renders_and_filters(db_path):
    at = _app(db_path).run()
    assert not at.exception
    assert any("companies" in c.value for c in at.caption)
    at.button[0].click().run()  # Add filter: bvps.cagr >= 0.10
    assert not at.exception
    table = at.dataframe[0].value
    assert set(table["ticker"]) == {"FAST", "BLK"}  # BLK: 2 years of ~17% growth


def test_company_page_renders(db_path, prices_dir):
    at = _app(db_path, prices_dir)
    at.session_state["page"] = "Company"
    at.session_state["company"] = 900001
    at.run()
    assert not at.exception
    assert at.header[0].value.endswith(")")
    assert "Price ratios" in [s.value for s in at.subheader]
    assert any("fiscal year 2024" in c.value for c in at.caption)


def test_portfolio_page_allocates(db_path, prices_dir):
    from test_portfolio import FILE

    from screener.portfolio import PORTFOLIO_DISCLAIMER, Portfolio

    at = _app(db_path, prices_dir)
    at.session_state["page"] = "Portfolio"
    at.session_state["portfolio"] = Portfolio.loads(FILE)
    at.run()
    assert not at.exception
    assert at.warning[0].value == PORTFOLIO_DISCLAIMER
    assert "Allocation at 0.5 Kelly" in [s.value for s in at.subheader]
    at.text_input(key="add_ticker").input("KO")
    at.button(key="add_ticker_button").click().run()
    assert not at.exception
    assert "KO" in at.session_state["portfolio"].tickers()
