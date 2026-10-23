from pathlib import Path

import pytest

from posse_bliki.cli import main


def test_build_writes_the_site_and_records_urls(vault: Path, tmp_path: Path) -> None:
    assert (
        main(
            [
                "--root",
                str(vault),
                "build",
                "--out",
                str(tmp_path / "o"),
                "--update-urls",
            ]
        )
        == 0
    )
    assert "/posts/first-post/" in (vault / "urls.lock").read_text().split()
    assert (tmp_path / "o" / "feed.xml").exists()


def test_check_fails_with_the_problems_listed(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "content/posts/bad.md").write_text("---\ntitle: Bad\n---\n")
    assert main(["--root", str(vault), "check"]) == 1
    assert "bad.md: date is required" in capsys.readouterr().err


def test_check_fails_when_a_published_url_disappears(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "urls.lock").write_text("/posts/gone/\n")
    assert main(["--root", str(vault), "check"]) == 1
    assert "/posts/gone/ was published and is gone" in capsys.readouterr().err


def test_webmention_dry_run_counts_external_links(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "content/posts/fresh.md").write_text(
        "---\ntitle: Fresh\ndate: 2999-01-01\n---\n[x](https://other.example/a)\n"
    )
    assert main(["--root", str(vault), "webmention", "--dry-run"]) == 0
    assert "fresh/: would notify 1 targets" in capsys.readouterr().out
