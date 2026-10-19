import io
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from mle_lab import data, features
from mle_lab.config import HORIZON, TARGET, TRADING_DAYS, Paths


def test_fetch_downloads_each_series(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = []

    def fake_urlopen(url: str, timeout: int) -> io.BytesIO:
        urls.append(url)
        return io.BytesIO(b"observation_date,X\n2026-01-02,1\n")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    paths = Paths(tmp_path)
    data.fetch(paths)
    assert sorted(p.name for p in paths.raw.iterdir()) == ["SP500.csv", "VIXCLS.csv"]
    assert all(u.startswith("https://fred.stlouisfed.org/") for u in urls)


def test_load_keeps_days_both_series_have(lab: Paths) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        prices = con.execute("SELECT * FROM prices").df()
    assert len(prices) == 799  # One holiday dropped.
    assert prices.notna().all().all()


def tiny(tmp_path: Path, closes: list[float]) -> duckdb.DuckDBPyConnection:
    tmp_path.mkdir(exist_ok=True)
    dates = pd.bdate_range("2026-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    pd.DataFrame({"observation_date": dates, "SP500": closes}).to_csv(tmp_path / "SP500.csv", index=False)
    pd.DataFrame({"observation_date": dates, "VIXCLS": 20.0}).to_csv(tmp_path / "VIXCLS.csv", index=False)
    con = duckdb.connect()
    data.load(con, tmp_path)
    features.build(con)
    return con


def test_volatility_is_annualized_from_daily_log_returns(tmp_path: Path) -> None:
    # Alternating +1% and -1% moves: every daily log return has the same size.
    closes = [100.0]
    for i in range(40):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 1 / 1.01))
    con = tiny(tmp_path, closes)
    row = con.execute("SELECT * FROM features ORDER BY day LIMIT 1").df().iloc[0]
    expected = 0.00995033 * TRADING_DAYS**0.5
    assert row.rv_5d == pytest.approx(expected, rel=1e-4)
    assert row.rv_21d == pytest.approx(expected, rel=1e-4)
    assert row.vix == pytest.approx(0.20)


def test_labels_wait_for_the_next_five_days(tmp_path: Path) -> None:
    con = tiny(tmp_path, [100 * 1.001**i for i in range(40)])
    targets = con.execute(f"SELECT {TARGET} FROM features ORDER BY day").df()[TARGET]
    assert targets.tail(HORIZON).isna().all()
    assert targets.iloc[:-HORIZON].notna().all()


def test_features_never_see_the_future(tmp_path: Path) -> None:
    """A crash after day t changes t's label but none of t's features."""
    calm = [100 * 1.001**i for i in range(60)]
    crash = calm[:50] + [c * 0.8 for c in calm[50:]]
    before, after = tiny(tmp_path / "calm", calm), tiny(tmp_path / "crash", crash)
    query = "SELECT * FROM features WHERE date = (SELECT date FROM prices ORDER BY date LIMIT 1 OFFSET 47)"
    a, b = before.execute(query).df(), after.execute(query).df()
    pd.testing.assert_frame_equal(a.drop(columns=[TARGET]), b.drop(columns=[TARGET]))
    assert b[TARGET].iloc[0] > a[TARGET].iloc[0]


def test_quality_checks_pass_on_good_data_and_catch_short_history(lab: Paths, tmp_path: Path) -> None:
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        assert features.check(con) == []
    short = tiny(tmp_path, [100 * 1.001**i for i in range(60)])
    assert "fewer than a year of rows" in features.check(short)
