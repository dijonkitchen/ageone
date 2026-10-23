"""Build the vault into the static site."""

from __future__ import annotations

import shutil
from collections import defaultdict
from dataclasses import replace
from html import escape
from pathlib import Path

from posse_bliki import feeds
from posse_bliki.content import Entry, Site, load_site, load_vault, normalize_alias
from posse_bliki.render import entry_html, layout, render_entries

URLS_FILE = "urls.lock"


def redirect_html(site: Site, target: str) -> str:
    url = escape(site.url + target)
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f'<title>Redirecting</title><link rel="canonical" href="{url}">'
        f'<meta http-equiv="refresh" content="0; url={url}"><meta name="robots" content="noindex">'
        f'</head><body><a href="{url}">Moved here</a></body></html>\n'
    )


def build(root: Path, out: Path, *, url: str | None = None) -> list[str]:
    """Write the site to `out` and return every published path (pages, redirects, tag pages, feeds excluded)."""
    site = load_site(root / "site.toml")
    if url:
        site = replace(site, url=url.rstrip("/"))
    vault = root / "content"
    entries = load_vault(vault)
    bodies = render_entries(site, entries)
    webmention = site.webmention_endpoint

    files: dict[
        str, str
    ] = {}  # path below the site root (a directory path or a file name) to content
    posts = [e for e in entries if e.kind == "post"]
    notes = sorted(
        (e for e in entries if e.kind == "note"), key=lambda e: e.title.lower()
    )
    published: list[str] = ["/"]

    def put(path: str, title: str, body: str) -> None:
        files[path] = layout(site, title, body, path=path, webmention=webmention)
        published.append(path)

    for entry in entries:
        article = entry_html(site, entry, bodies[entry.path], level=1)
        put(entry.path, entry.title, article)
        for alias in entry.aliases:
            files[normalize_alias(alias)] = redirect_html(site, entry.path)

    feed = (
        "".join(entry_html(site, p, bodies[p.path]) for p in posts)
        or "<p>No posts yet.</p>\n"
    )
    hfeed = f'<div class="h-feed">\n<h1 class="p-name">{escape(site.title)}</h1>\n{feed}</div>\n'
    files["/"] = layout(site, site.title, hfeed, path="/", webmention=webmention)

    note_list = "".join(
        f'<li><a href="{site.base}{n.path}">{escape(n.title)}</a></li>\n' for n in notes
    )
    put("/notes/", "Notes", f"<h1>Notes</h1>\n<ul>\n{note_list}</ul>\n")

    by_tag: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        if entry.kind != "page":
            for tag in entry.tags:
                by_tag[tag].append(entry)
    tag_list = "".join(
        f'<li><a href="{site.base}/tags/{t}/">{t}</a> ({len(by_tag[t])})</li>\n'
        for t in sorted(by_tag)
    )
    put("/tags/", "Tags", f"<h1>Tags</h1>\n<ul>\n{tag_list}</ul>\n")
    for tag, tagged in sorted(by_tag.items()):
        items = "".join(
            f'<li><a href="{site.base}{e.path}">{escape(e.title)}</a></li>\n'
            for e in tagged
        )
        put(
            f"/tags/{tag}/",
            f"Tagged {tag}",
            f"<h1>Tagged {escape(tag)}</h1>\n<ul>\n{items}</ul>\n",
        )

    files["/404.html"] = layout(
        site,
        "Not found",
        f'<h1>Not found</h1>\n<p>That page does not exist. <a href="{site.base}/">Start at the blog</a>.</p>\n',
        path="/404.html",
    )
    sitemap_entries = [(path, None) for path in published if path != "/"]
    when = {e.path: e.published for e in entries}
    files["/sitemap.xml"] = feeds.sitemap(
        site, [("/", None)] + [(p, when.get(p)) for p, _ in sitemap_entries]
    )
    files["/robots.txt"] = feeds.robots(site)
    files["/feed.xml"] = feeds.rss(site, posts, bodies)
    files["/feed.json"] = feeds.json_feed(site, posts, bodies)

    if out.exists():
        shutil.rmtree(out)
    for path, content in files.items():
        target = out / path.lstrip("/")
        if path.endswith("/"):
            target = target / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    assets = root / "content" / "assets"
    if assets.is_dir():
        shutil.copytree(assets, out / "assets")
    return sorted(
        {*published, *(normalize_alias(a) for e in entries for a in e.aliases)}
    )


def check_urls(root: Path, paths: list[str]) -> list[str]:
    """Stable URLs: every path in urls.lock must still be published (as a page or a redirect)."""
    lock = root / URLS_FILE
    if not lock.exists():
        return []
    promised = [
        line.strip()
        for line in lock.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    have = set(paths)
    return [
        f"{URLS_FILE}: {p} was published and is gone; keep it or add it as an alias"
        for p in promised
        if p not in have
    ]


def update_urls(root: Path, paths: list[str]) -> None:
    lock = root / URLS_FILE
    known = set(lock.read_text(encoding="utf-8").split()) if lock.exists() else set()
    lock.write_text("\n".join(sorted(known | set(paths))) + "\n", encoding="utf-8")
