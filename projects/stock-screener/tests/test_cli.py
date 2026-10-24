import json

from test_screen import SCREEN

from screener import DISCLAIMER
from screener.cli import main


def test_screen_json_and_csv(db_path, tmp_path, capsys):
    path = tmp_path / "s.toml"
    path.write_text(SCREEN)
    main(["--db", str(db_path), "screen", str(path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["disclaimer"] == DISCLAIMER
    assert [r["ticker"] for r in payload["rows"]] == ["FAST", "SLOW"]
    assert "Book value per share" in payload["definitions"]["bvps.cagr"]

    main(["--db", str(db_path), "screen", str(path), "--format", "csv"])
    out = capsys.readouterr().out
    assert out.startswith(f"# {DISCLAIMER}")
    assert "ticker,name" in out

    main(["--db", str(db_path), "screen", str(path)])
    assert "FAST" in capsys.readouterr().out


def test_company(db_path, capsys):
    main(["--db", str(db_path), "company", "FAST"])
    out = capsys.readouterr().out
    assert "Example Compounding Corp" in out and "Splits:" in out and DISCLAIMER in out
    main(["--db", str(db_path), "company", "FAST", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["series"]) == 14 and len(payload["filings"]) == 14


def test_spot_check(db_path, tmp_path, capsys):
    path = tmp_path / "spot.toml"
    path.write_text('tolerance = 0.01\n[[companies]]\nticker = "FAST"\n[companies.values.roe]\n2024 = 0.1237\n')
    try:
        main(["--db", str(db_path), "spot-check", str(path)])
    except SystemExit as exit:
        assert exit.code == 0, capsys.readouterr().out


def test_quotes_ratios_portfolio_and_live_screen(db_path, prices_dir, tmp_path, capsys):
    from test_portfolio import FILE

    common = ["--db", str(db_path), "--prices-db", str(tmp_path / "p.duckdb"), "--prices-dir", str(prices_dir)]
    main([*common, "quotes", "FAST,SLOW", "BLK", "--format", "json"])
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert {r["ticker"]: r["delay"] for r in rows} == {"BLK": "last close", "FAST": "last close", "SLOW": "last close"}
    assert all(r["source"] and r["timestamp"] for r in rows)

    main([*common, "ratios", "FAST", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["live"]["live.fiscal_year"] == 2024
    assert {r["ratio"] for r in payload["ranges"]} == {"P/E", "P/B", "P/FCF", "Dividend yield"}

    path = tmp_path / "s.toml"
    path.write_text('window = "10"\n[[filters]]\ncolumn = "live.pb"\nop = "<="\nvalue = 8.0\n')
    main([*common, "screen", str(path), "--quotes", "--format", "json"])
    assert [r["ticker"] for r in json.loads(capsys.readouterr().out)["rows"]] == ["BLK", "FAST"]

    book = tmp_path / "p.toml"
    book.write_text(FILE)
    main([*common, "portfolio", str(book), "--value", "50000"])
    captured = capsys.readouterr()
    out = captured.out
    assert "cash left" in out, captured.err and "full Kelly" in out and "not investment advice" in out.replace("\n", " ").lower()
