"""RSS 2.0, JSON Feed 1.1, the sitemap, and robots.txt."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from posse_bliki.content import Entry, Site


def absolutize(site: Site, html: str) -> str:
    """Feed readers have no base URL: make root-relative links absolute."""
    parts = urlparse(site.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    return html.replace('href="/', f'href="{origin}/').replace(
        'src="/', f'src="{origin}/'
    )


def _updated(posts: list[Entry]) -> datetime:
    return max(
        (p.published for p in posts if p.published),
        default=datetime(1970, 1, 1, tzinfo=UTC),
    )


def rss(site: Site, posts: list[Entry], bodies: dict[str, str]) -> str:
    items = []
    for post in posts:
        assert post.published
        url = site.url + post.path
        items.append(
            "<item>"
            f"<title>{escape(post.title)}</title><link>{escape(url)}</link>"
            f'<guid isPermaLink="true">{escape(url)}</guid>'
            f"<pubDate>{format_datetime(post.published)}</pubDate>"
            + "".join(f"<category>{escape(t)}</category>" for t in post.tags)
            + (
                f"<description>{escape(post.summary)}</description>"
                if post.summary
                else ""
            )
            + f"<content:encoded>{escape(absolutize(site, bodies[post.path]))}</content:encoded>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        f"<channel><title>{escape(site.title)}</title><link>{escape(site.url)}/</link>"
        f"<description>{escape(site.description or site.title)}</description><language>{escape(site.language)}</language>"
        f'<atom:link href="{escape(site.url)}/feed.xml" rel="self" type="application/rss+xml"/>'
        f"<lastBuildDate>{format_datetime(_updated(posts))}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )


def json_feed(site: Site, posts: list[Entry], bodies: dict[str, str]) -> str:
    items = []
    for post in posts:
        assert post.published
        item: dict[str, object] = {
            "id": site.url + post.path,
            "url": site.url + post.path,
            "title": post.title,
            "content_html": absolutize(site, bodies[post.path]),
            "date_published": post.published.isoformat(),
            "tags": post.tags,
        }
        if post.summary:
            item["summary"] = post.summary
        items.append(item)
    author: dict[str, str] = {"name": site.author.name}
    if site.author.url:
        author["url"] = site.author.url
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": site.title,
        "home_page_url": site.url + "/",
        "feed_url": site.url + "/feed.json",
        "language": site.language,
        "authors": [author],
        "items": items,
    }
    if site.description:
        feed["description"] = site.description
    return json.dumps(feed, indent=2, ensure_ascii=False) + "\n"


def sitemap(site: Site, paths: list[tuple[str, datetime | None]]) -> str:
    rows = "".join(
        f"<url><loc>{escape(site.url + path)}</loc>"
        + (f"<lastmod>{when.date().isoformat()}</lastmod>" if when else "")
        + "</url>"
        for path, when in paths
    )
    return f'<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>\n'


def robots(site: Site) -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {site.url}/sitemap.xml\n"
