import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import feedparser
import mf2py
import pytest

from posse_bliki.build import build, check_urls, update_urls
from posse_bliki.content import ContentError

from .conftest import write_vault

BASE = "https://example.org/b"


def html(out: Path, path: str) -> str:
    return (out / path.strip("/") / "index.html").read_text(encoding="utf-8")


def parse(out: Path, path: str) -> Any:
    return mf2py.parse(doc=html(out, path), url=BASE + path)


def test_output_contract_files_exist(built: Path) -> None:
    for name in (
        "index.html",
        "404.html",
        "robots.txt",
        "sitemap.xml",
        "feed.xml",
        "feed.json",
    ):
        assert (built / name).is_file(), name
    for path in (
        "/posts/first-post/",
        "/posts/second-post/",
        "/notes/a-note/",
        "/another-page/",
        "/notes/",
        "/tags/",
        "/tags/meta/",
        "/tags/other/",
    ):
        assert (built / path.strip("/") / "index.html").is_file(), path


def test_drafts_are_not_built(built: Path) -> None:
    assert not (built / "posts" / "unfinished").exists()
    assert "unfinished" not in (built / "feed.xml").read_text()


def test_aliases_redirect_to_the_canonical_url(built: Path) -> None:
    page = html(built, "/old/first/")
    assert f'rel="canonical" href="{BASE}/posts/first-post/"' in page
    assert f'http-equiv="refresh" content="0; url={BASE}/posts/first-post/"' in page


def test_wiki_links_resolve_and_code_is_untouched(built: Path) -> None:
    page = html(built, "/posts/first-post/")
    assert 'href="/b/notes/a-note/"' in page
    assert '<a href="/b/another-page/">the page</a>' in page
    assert "[[not-a-link]]" in page


def test_backlinks_list_the_linking_entries(built: Path) -> None:
    assert "Linked from" in html(built, "/notes/a-note/")
    assert 'href="/b/posts/first-post/"' in html(built, "/notes/a-note/")


def test_post_is_an_h_entry_with_author_and_syndication(built: Path) -> None:
    data = parse(built, "/posts/first-post/")
    entry = next(i for i in data["items"] if "h-entry" in i["type"])
    props = entry["properties"]
    assert props["name"] == ["First post"]
    assert props["published"][0].startswith("2026-01-02")
    assert props["url"] == [f"{BASE}/posts/first-post/"]
    assert props["category"] == ["meta"]
    assert props["syndication"] == ["https://social.example/ada/1"]
    assert props["author"][0]["properties"]["name"] == ["Ada"]
    assert "Hello" in props["content"][0]["value"]


def test_home_is_an_h_feed_of_posts_newest_first(built: Path) -> None:
    data = parse(built, "/")
    feed = next(i for i in data["items"] if "h-feed" in i["type"])
    names = [
        c["properties"]["name"][0] for c in feed["children"] if "h-entry" in c["type"]
    ]
    assert names == ["Second post", "First post"]


def test_every_page_has_an_h_card_and_webmention_endpoint(built: Path) -> None:
    page = html(built, "/notes/a-note/")
    assert any("h-card" in i["type"] for i in parse(built, "/notes/a-note/")["items"])
    assert '<link rel="webmention" href="https://webmention.example/endpoint">' in page


def test_rss_is_well_formed_and_parses(built: Path) -> None:
    ET.fromstring((built / "feed.xml").read_text())
    feed = feedparser.parse(str(built / "feed.xml"))
    assert not feed.bozo
    assert [e.title for e in feed.entries] == ["Second post", "First post"]
    first = feed.entries[1]
    assert first.link == f"{BASE}/posts/first-post/" and first.id == first.link
    assert 'href="https://example.org/b/notes/a-note/"' in first.content[0].value
    assert feed.entries[0].published_parsed is not None


def test_json_feed_follows_version_1_1(built: Path) -> None:
    feed = json.loads((built / "feed.json").read_text())
    assert feed["version"] == "https://jsonfeed.org/version/1.1"
    assert (
        feed["feed_url"] == f"{BASE}/feed.json" and feed["home_page_url"] == f"{BASE}/"
    )
    assert [i["title"] for i in feed["items"]] == ["Second post", "First post"]
    for item in feed["items"]:
        assert item["id"] and ("content_html" in item or "content_text" in item)
        assert item["date_published"].endswith("+00:00")


def test_sitemap_and_robots(built: Path) -> None:
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [
        e.text
        for e in ET.fromstring((built / "sitemap.xml").read_text()).findall(
            "s:url/s:loc", ns
        )
    ]
    assert (
        f"{BASE}/" in locs
        and f"{BASE}/posts/first-post/" in locs
        and f"{BASE}/tags/meta/" in locs
    )
    assert not any(
        "old/first" in (loc or "") for loc in locs
    )  # redirects are not canonical
    assert f"Sitemap: {BASE}/sitemap.xml" in (built / "robots.txt").read_text()


def test_unresolved_wiki_link_fails_the_build(vault: Path, tmp_path: Path) -> None:
    (vault / "content/notes/a-note.md").write_text(
        "---\ntitle: A note\n---\nSee [[missing]].\n"
    )
    with pytest.raises(ContentError, match="unresolved wiki link \\[\\[missing\\]\\]"):
        build(vault, tmp_path / "out")


def test_base_url_override_rewrites_links(vault: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build(vault, out, url="http://localhost:8000")
    assert 'href="/notes/a-note/"' in html(out, "/posts/first-post/")


def test_published_urls_are_stable(vault: Path, tmp_path: Path) -> None:
    (vault / "content/notes/gone-note.md").write_text("---\ntitle: Gone\n---\nx\n")
    paths = build(vault, tmp_path / "out")
    update_urls(vault, paths)
    assert check_urls(vault, paths) == []
    (vault / "content/notes/gone-note.md").unlink()
    (vault / "content/notes/b-note.md").write_text("---\ntitle: B\n---\nx\n")
    paths = build(vault, tmp_path / "out2")
    assert any("/notes/gone-note/" in p for p in check_urls(vault, paths))
    (vault / "content/notes/b-note.md").write_text(
        "---\ntitle: B\naliases: [/notes/gone-note/]\n---\nx\n"
    )
    assert check_urls(vault, build(vault, tmp_path / "out3")) == []


def test_empty_vault_builds(tmp_path: Path) -> None:
    out = tmp_path / "out"
    build(write_vault(tmp_path / "v", {}), out)
    assert "No posts yet" in (out / "index.html").read_text()
