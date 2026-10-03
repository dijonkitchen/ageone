from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "src" / "screener" / "app.py")


def _app(db_path):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = "Screen"
    import sys

    sys.argv = ["app.py", "--db", str(db_path)]
    return at


def test_screen_page_renders_and_filters(db_path):
    at = _app(db_path).run()
    assert not at.exception
    assert any("companies" in c.value for c in at.caption)
    at.button[0].click().run()  # Add filter: bvps.cagr >= 0.10
    assert not at.exception
    table = at.dataframe[0].value
    assert set(table["ticker"]) == {"FAST", "BLK"}  # BLK: 2 years of ~17% growth


def test_company_page_renders(db_path):
    at = _app(db_path)
    at.session_state["page"] = "Company"
    at.run()
    assert not at.exception
    assert at.header[0].value.endswith(")")
