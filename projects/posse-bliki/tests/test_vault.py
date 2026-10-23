"""The committed vault builds, and its URLs match urls.lock."""

from pathlib import Path

import mf2py

from posse_bliki.build import build, check_urls

ROOT = Path(__file__).resolve().parent.parent


def test_committed_vault_builds_and_keeps_its_urls(tmp_path: Path) -> None:
    paths = build(ROOT, tmp_path)
    assert check_urls(ROOT, paths) == []
    assert (ROOT / "urls.lock").exists(), (
        "run `uv run bliki build --update-urls` after adding pages"
    )
    locked = set((ROOT / "urls.lock").read_text().split())
    assert set(paths) <= locked | set(paths), "unreachable"
    assert not set(paths) - locked, (
        f"unlocked URLs: run `uv run bliki build --update-urls` ({sorted(set(paths) - locked)})"
    )


def test_committed_posts_parse_as_h_entries(tmp_path: Path) -> None:
    build(ROOT, tmp_path)
    for page in (tmp_path / "posts").glob("*/index.html"):
        items = mf2py.parse(doc=page.read_text(), url="https://example.org/")["items"]
        assert any("h-entry" in i["type"] for i in items), page
